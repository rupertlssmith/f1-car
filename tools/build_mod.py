#!/usr/bin/env python3
"""Package a BeamNG vehicle mod from this repo into an installable .zip.

The zip mirrors the game's mod layout, so it can be dropped straight into the
BeamNG.drive mods folder:

    vehicles/<mod>/...                  the vehicle itself
    vehicles/common/<mod>_*/...         shared parts it owns (e.g. wheels)
    mod_info/<mod>/...                  the manifest (info.json, icon, images)

The zip is always named <mod>.zip, so installing a new build replaces the
old one in the game's mods folder. (Until round 12 builds were named
<mod>_YYYYMMDD-HHMMSS.zip; several of those left side by side in the mods
folder all load, and the game shows the configurations of every one --
delete them.) --stamp adds the timestamp back for keeping archive copies.

--test packs a test build: only Baseline and the test-car variants
(fix_* / steer_* / rear_* / test_* / drift_* / hub_* / wob_* / shim_*), without the other setups (Low / High Downforce, Aggressive).

The manifest's "hashes" list (xxHash64 of every file under vehicles/) is
regenerated for the files actually packed, so it never goes stale.

Usage:
    python3 tools/build_mod.py                  # builds dist/redbull.zip
    python3 tools/build_mod.py --test           # Baseline + Front Fix cars only
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
                    help="leave out the test-car variants (fix_* / steer_* / rear_* / test_* / drift_* / hub_* / wob_* / shim_*, tools/rb14/variants.py)")
    ap.add_argument("--test", action="store_true",
                    help="test build: only Baseline and the test-car variants (fix_* / steer_* / rear_* / test_* / drift_* / hub_* / wob_* / shim_*)")
    ap.add_argument("--stamp", action="store_true",
                    help="name the zip <mod>_YYYYMMDD-HHMMSS.zip instead of <mod>.zip")
    ap.add_argument("--no-check", action="store_true",
                    help="skip tools/check_mod.py (by default a build with model errors is refused)")
    args = ap.parse_args()

    if not args.no_check:
        import subprocess
        res = subprocess.run([sys.executable, os.path.join(REPO, "tools", "check_mod.py"), "--mod", args.mod],
                             cwd=REPO, capture_output=True, text=True)
        print(res.stdout.strip().splitlines()[-1] if res.stdout.strip() else res.stderr.strip())
        if "ModuleNotFoundError" in res.stderr:
            sys.exit("the model check needs a Python package that is not installed (%s): see README.md "
                     "(e.g. pip install numpy), or build with --no-check"
                     % res.stderr.strip().splitlines()[-1])
        if res.returncode != 0:
            print("\n".join(l for l in res.stdout.splitlines() if l.startswith("ERROR")))
            sys.exit("check_mod.py found errors: not building (--no-check to build anyway)")

    files = list_files(mod_dirs(args.mod))
    if args.no_variants:
        files = [f for f in files if not os.path.basename(f).startswith(("fix_", "info_fix_", "steer_", "info_steer_", "rear_", "info_rear_", "test_", "info_test_", "drift_", "info_drift_", "hub_", "info_hub_", "wob_", "info_wob_", "shim_", "info_shim_"))]
    if args.test:
        # a configuration is <name>.pc + <name>.jpg/.png + info_<name>.json
        vdir = f"vehicles/{args.mod}/"
        configs = {os.path.basename(f)[:-3] for f in files if f.startswith(vdir) and f.endswith(".pc")}
        keep = {c for c in configs if c == "baseline" or c.startswith(("fix_", "steer_", "rear_", "test_", "drift_", "hub_", "wob_", "shim_"))}

        def config_of(f):
            if not f.startswith(vdir) or "/" in f[len(vdir):]:
                return None
            stem = os.path.splitext(os.path.basename(f))[0]
            stem = stem[len("info_"):] if stem.startswith("info_") else stem
            return stem if stem in configs else None
        files = [f for f in files if config_of(f) is None or config_of(f) in keep]
    manifest_rel = f"mod_info/{args.mod}/info.json"
    info = build_manifest(args.mod, files)
    manifest = json.dumps(info, indent=4, ensure_ascii=False) + "\n"

    out_dir = os.path.join(REPO, args.out)
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    zip_path = os.path.join(out_dir, f"{args.mod}_{stamp}.zip" if args.stamp else f"{args.mod}.zip")
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
    configs = sorted(os.path.basename(f)[:-3] for f in files if f.startswith(f"vehicles/{args.mod}/") and f.endswith(".pc"))
    print(f"built {os.path.relpath(zip_path, REPO)}: {len(files)} files, "
          f"{size_mb:.1f} MB; configurations: {', '.join(configs)}")


if __name__ == "__main__":
    main()
