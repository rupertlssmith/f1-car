"""Small, targeted text edits to jbeam files that keep their formatting,
comments and CRLF line endings (the files stay diff-friendly).

    set_node_option(path, node_id, key, value)   # e.g. nodeWeight
    replace_once(path, old, new)                 # exact text, must match once
"""
import json
import re


def _read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def set_node_option(path, node_id, key, value):
    """Set an inline option on a node row: ["id", x, y, z, {...key: value}]."""
    text = _read(path)
    num = r'(?:-?(?:\d+\.?\d*|\.\d+)|"\$=[^"]*")'      # a coordinate: number or "$=expr"
    pat = re.compile(r'(\[\s*"' + re.escape(node_id) + r'"\s*,\s*' + num + r'\s*,\s*' + num + r'\s*,\s*' + num + r')(\s*,\s*\{([^{}]*)\})?(\s*\])')
    m = pat.search(text)
    if not m:
        raise KeyError(f"node {node_id} not found in {path}")
    opts = m.group(3)
    val = json.dumps(value)
    if opts is None:
        new = f'{m.group(1)}, {{"{key}":{val}}}{m.group(4)}'
    elif re.search(r'"' + re.escape(key) + r'"\s*:', opts):
        new_opts = re.sub(r'("' + re.escape(key) + r'"\s*:\s*)("[^"]*"|[^,}]+)', lambda mm: mm.group(1) + val, opts)
        new = f"{m.group(1)}{m.group(2).replace(opts, new_opts)}{m.group(4)}"
    else:
        sep = ", " if opts.strip() else ""
        added = "{" + opts + sep + '"' + key + '":' + val + "}"
        new = m.group(1) + m.group(2).replace("{" + opts + "}", added) + m.group(4)
    if len(pat.findall(text)) != 1:
        raise ValueError(f"node {node_id} matches more than once in {path}")
    _write(path, text[:m.start()] + new + text[m.end():])


def replace_once(path, old, new):
    text = _read(path)
    n = text.count(old)
    if n != 1:
        raise ValueError(f"{path}: expected 1 match, found {n}: {old[:60]!r}")
    _write(path, text.replace(old, new))


def replace_all(path, old, new):
    text = _read(path)
    if old not in text:
        raise ValueError(f"{path}: no match for {old[:60]!r}")
    _write(path, text.replace(old, new))


def set_all(path, pattern, new):
    """Replace every regex match with new (idempotent when new matches the
    pattern too). Raises if nothing matches."""
    text = _read(path)
    out, n = re.subn(pattern, lambda m: new, text)
    if n == 0:
        raise ValueError(f"{path}: no match for {pattern!r}")
    _write(path, out)


def set_in_part(path, part, pattern, new):
    """set_all() restricted to one part's block of a jbeam file."""
    import jbeam as _jb   # tools/ must be on sys.path
    text = _read(path)
    names = list(_jb.loads(text, path).keys())
    def key_at(name, frm=0):
        m = re.compile(r'"' + re.escape(name) + r'"\s*:\s*\{').search(text, frm)
        return m.start() if m else None
    start = key_at(part)
    ends = [e for e in (key_at(n, start + 1) for n in names if n != part) if e is not None]
    end = min(ends) if ends else len(text)
    block, n = re.subn(pattern, lambda m: new, text[start:end])
    if n == 0:
        raise ValueError(f"{path}:{part}: no match for {pattern!r}")
    _write(path, text[:start] + block + text[end:])
