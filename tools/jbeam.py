"""Tolerant reader for BeamNG .jbeam files (and the relaxed JSON BeamNG uses
for .pc / materials files).

jbeam is JSON with extras: // and /* */ comments, trailing commas, and
commas that may be missing between elements. json.loads rejects all of
those, so this is a small hand-written parser that accepts them.

    import jbeam
    parts = jbeam.load("vehicles/redbull/redbull_body.jbeam")   # {part: {...}}

Section tables such as "nodes" or "beams" are lists whose first row is a
header (["id", "posX", "posY", "posZ"]); rows may be interleaved with
option dicts ({"nodeWeight": 2}) that apply to the rows after them.
table_rows() expands that into dicts with the options merged in.
"""
import re

_NUM = re.compile(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


class JbeamError(ValueError):
    pass


class _Parser:
    def __init__(self, text, name):
        self.s = text
        self.i = 0
        self.name = name

    def err(self, msg):
        line = self.s.count("\n", 0, self.i) + 1
        raise JbeamError(f"{self.name}:{line}: {msg}")

    def ws(self):
        s, n = self.s, len(self.s)
        while self.i < n:
            c = s[self.i]
            if c in " \t\r\n,":          # commas are optional separators
                self.i += 1
            elif s.startswith("//", self.i):
                j = s.find("\n", self.i)
                self.i = n if j < 0 else j + 1
            elif s.startswith("/*", self.i):
                j = s.find("*/", self.i + 2)
                if j < 0:
                    self.err("unterminated comment")
                self.i = j + 2
            else:
                break

    def value(self):
        self.ws()
        if self.i >= len(self.s):
            self.err("unexpected end of file")
        c = self.s[self.i]
        if c == "{":
            return self.obj()
        if c == "[":
            return self.arr()
        if c == '"':
            return self.string()
        m = _NUM.match(self.s, self.i)
        if m:
            self.i = m.end()
            t = m.group()
            return float(t) if any(ch in t for ch in ".eE") else int(t)
        for word, val in (("true", True), ("false", False), ("null", None)):
            if self.s.startswith(word, self.i):
                self.i += len(word)
                return val
        self.err(f"unexpected character {c!r}")

    def string(self):
        self.i += 1
        out = []
        s = self.s
        while True:
            j = self.i
            while j < len(s) and s[j] not in '"\\':
                j += 1
            out.append(s[self.i:j])
            if j >= len(s):
                self.err("unterminated string")
            if s[j] == '"':
                self.i = j + 1
                return "".join(out)
            esc = s[j + 1]
            out.append({"n": "\n", "t": "\t", "r": "\r", "b": "\b",
                        "f": "\f", "/": "/", "\\": "\\", '"': '"'}.get(esc, esc))
            if esc == "u":
                out[-1] = chr(int(s[j + 2:j + 6], 16))
                self.i = j + 6
            else:
                self.i = j + 2

    def obj(self):
        self.i += 1
        d = {}
        while True:
            self.ws()
            if self.i >= len(self.s):
                self.err("unterminated object")
            if self.s[self.i] == "}":
                self.i += 1
                return d
            if self.s[self.i] != '"':
                self.err("expected key")
            k = self.string()
            self.ws()
            if self.i < len(self.s) and self.s[self.i] == ":":
                self.i += 1
            else:
                self.err("expected ':'")
            d[k] = self.value()

    def arr(self):
        self.i += 1
        a = []
        while True:
            self.ws()
            if self.i >= len(self.s):
                self.err("unterminated array")
            if self.s[self.i] == "]":
                self.i += 1
                return a
            a.append(self.value())


def loads(text, name="<string>"):
    p = _Parser(text, name)
    v = p.value()
    p.ws()
    if p.i != len(p.s):
        p.err("trailing data")
    return v


def load(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return loads(fh.read(), path)


def table_rows(table):
    """Expand a jbeam section table into dicts, with inline option rows
    merged into the rows that follow them. Returns [] for non-tables."""
    if not isinstance(table, list) or not table or not isinstance(table[0], list):
        return []
    header = table[0]
    opts = {}
    rows = []
    for row in table[1:]:
        if isinstance(row, dict):
            opts = {**opts, **row}
            continue
        if not isinstance(row, list):
            continue
        r = dict(opts)
        for k, v in zip(header, row):
            r[k] = v
        # A trailing dict past the header columns holds per-row options.
        if len(row) > len(header) and isinstance(row[-1], dict):
            r.update(row[-1])
        rows.append(r)
    return rows
