#!/usr/bin/env python3
"""Comment out jbeam flexbody/prop rows whose mesh no longer exists.

    python3 tools/rb14/sync_jbeam.py [--check]

After build_model.py, some F4 meshes are gone (replaced by the RB14 or
dropped). Their jbeam rows are commented out with a "// rb14: no mesh"
marker rather than deleted, so the physics is untouched and a row is easy to
restore if its mesh comes back. Base-game meshes (brakes) are left alone.
"""
import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import dae  # noqa: E402

DIRS = ["vehicles/redbull", "vehicles/common/redbull_wheels"]
MARK = "// rb14: no mesh "
ROW = re.compile(r'^(\s*)(\[\s*"([^"]*)"\s*,\s*(?:"([^"]+)"\s*,|\[).*)$')
BASE = re.compile(r"^(brake_|brakepad|disc_)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    os.chdir(REPO)
    meshes = {m.name for d in DIRS for f in glob.glob(f"{d}/*.dae") for m in dae.read(f)}
    total = 0
    for d in DIRS:
        for f in sorted(glob.glob(f"{d}/*.jbeam")):
            text = open(f, encoding="utf-8", newline="").read()
            out, section, changed = [], None, 0
            for line in text.split("\n"):
                m = re.match(r'\s*"(flexbodies|props)"\s*:', line)
                if m:
                    section = m.group(1)
                elif re.match(r'\s*"[A-Za-z0-9_]+"\s*:', line):
                    section = None
                r = ROW.match(line)
                if section and r:
                    # flexbody rows start with the mesh; prop rows with func, then mesh
                    mesh = r.group(3) if section == "flexbodies" else r.group(4)
                    if mesh and mesh not in ("mesh",) and mesh not in meshes and not BASE.match(mesh):
                        line = r.group(1) + MARK + r.group(2)
                        changed += 1
                out.append(line)
            if changed:
                total += changed
                print(f"{'would comment' if args.check else 'commented'} {changed} row(s) in {f}")
                if not args.check:
                    with open(f, "w", encoding="utf-8", newline="") as fh:
                        fh.write("\n".join(out))
    print(f"{total} row(s) {'to comment out' if args.check else 'commented out'}")


if __name__ == "__main__":
    main()
