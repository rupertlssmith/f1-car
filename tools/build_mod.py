#!/usr/bin/env python3
"""Package a BeamNG vehicle mod from this repo into an installable .zip.

The zip mirrors the game's mod layout, so it can be dropped straight into the
BeamNG.drive mods folder:

    vehicles/<mod>/...                  the vehicle itself
    vehicles/common/<mod>_*/...         shared parts it owns (e.g. wheels)
    mod_info/<mod>/...                  the manifest (info.json, icon, images)

The zip is named <mod>_YYYYMMDD-HHMMSS.zip (local time of the build) so
successive builds can be told apart. Keep only one of them in the game's mods
folder at a time: each is a full copy of the same vehicle.

The manifest's "hashes" list (xxHash64 of every file under vehicles/) is
regenerated for the files actually packed, so it never goes stale.

Usage:
    python3 tools/build_mod.py                  # builds dist/redbull_<timestamp>.zip
    python3 tools/build_mod.py --mod redbull --out dist
    python3 tools/build_mod.py --update-manifest   # also rewrite the hashes
                                                   # in mod_info/<mod>/info.json

Needs the `xxhash` Python package (pip install xxhash).
"""
import argparse
import datetime
import json
import os
import sys
import zipfile

try:
    import xxhash
except ImportError:
    sys.exit("build_mod: the 'xxhash' package is required (pip install xxhash)")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Editor/OS droppings that must never ship.
JUNK = {".DS_Store", "Thumbs.db", "desktop.ini"}


def mod_dirs(mod):
    """The repo directories (relative to REPO) that make up the mod."""
    dirs = [f"vehicles/{mod}", f"mod_info/{mod}"]
    common = os.path.join(REPO, "vehicles", "common")
    if os.path.isdir(common):
        dirs += [f"vehicles/common/{d}" for d in sorted(os.listdir(common))
                 if d.startswith(f"{mod}_")]
    for d in dirs:
        if not os.path.isdir(os.path.join(REPO, d)):
            sys.exit(f"build_mod: missing directory {d}")
    return dirs


def list_files(dirs):
    """All files under dirs, as sorted repo-relative POSIX paths."""
    out = []
    for d in dirs:
        for dirpath, dirnames, files in os.walk(os.path.join(REPO, d)):
            dirnames[:] = [n for n in dirnames if not n.startswith(".")]
            for f in files:
                if f in JUNK or f.startswith("."):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, f), REPO)
                out.append(rel.replace(os.sep, "/"))
    return sorted(out)


def file_hash(rel):
    h = xxhash.xxh64()
    with open(os.path.join(REPO, rel), "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(mod, files):
    path = os.path.join(REPO, "mod_info", mod, "info.json")
    with open(path, encoding="utf-8") as fh:
        info = json.load(fh)
    info["hashes"] = [[f, file_hash(f)] for f in files
                      if f.startswith("vehicles/")]
    return info


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mod", default="redbull", help="mod name (default: redbull)")
    ap.add_argument("--out", default="dist", help="output directory (default: dist)")
    ap.add_argument("--update-manifest", action="store_true",
                    help="write the regenerated hashes back to mod_info/<mod>/info.json")
    ap.add_argument("--no-variants", action="store_true",
                    help="leave out the front-fix test cars (fix_*.pc, tools/rb14/variants.py)")
    args = ap.parse_args()

    files = list_files(mod_dirs(args.mod))
    if args.no_variants:
        files = [f for f in files if not os.path.basename(f).startswith(("fix_", "info_fix_"))]
    manifest_rel = f"mod_info/{args.mod}/info.json"
    info = build_manifest(args.mod, files)
    manifest = json.dumps(info, indent=4, ensure_ascii=False) + "\n"

    out_dir = os.path.join(REPO, args.out)
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    zip_path = os.path.join(out_dir, f"{args.mod}_{stamp}.zip")
    tmp_path = zip_path + ".tmp"
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for rel in files:
            if rel == manifest_rel:
                zf.writestr(rel, manifest)
            else:
                zf.write(os.path.join(REPO, rel), rel)
    os.replace(tmp_path, zip_path)

    if args.update_manifest:
        with open(os.path.join(REPO, manifest_rel), "w", encoding="utf-8") as fh:
            fh.write(manifest)

    size_mb = os.path.getsize(zip_path) / 1e6
    print(f"built {os.path.relpath(zip_path, REPO)}: {len(files)} files, "
          f"{size_mb:.1f} MB")


if __name__ == "__main__":
    main()
