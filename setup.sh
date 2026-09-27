#!/usr/bin/env bash
# Initialise this starter as a new project: inject ${name} everywhere it matters.
#
#   ./setup.sh my-project              # rename, with a confirmation prompt
#   ./setup.sh my-project -y           # no prompt
#   ./setup.sh my-project --dry-run    # show what would change, touch nothing
#   ./setup.sh my-project --fresh-git  # also discard the starter's git history
#
# What it renames: the two image names (`<name>-runtime`, `<name>-dev`), both
# named volumes (`<name>-home`, `<name>-data`), the Compose project name, and
# every mention in the scripts and docs — everything that is currently the token
# `devbox`. It reads the CURRENT name out of docker/docker-compose.dev.yml rather
# than assuming `devbox`, so it is also how you rename a project later on: run it
# again with the new name.
#
# It deliberately does NOT delete itself after running, for that reason.
#
# What it does not do: rename the directory you cloned into, and rename Docker
# volumes you have already created. If you built and ran before renaming, the
# volume under the OLD name is still on the daemon — `docker volume ls` will show
# it, and it is yours to remove or ignore.
set -eu

cd "$(dirname "$0")"

SELF="$(basename "$0")"

usage() {
  cat >&2 <<USAGE
usage: ./${SELF} <name> [-y] [--dry-run] [--fresh-git]

  <name>        lowercase letters, digits and hyphens; must start alphanumeric.
                Used for image names, volume names and the Compose project.

  -y, --yes     do not prompt for confirmation
  -n, --dry-run print what would change and exit without writing
  --fresh-git   after renaming, discard the starter's history and make this
                repo's first commit (destructive; asks first unless -y)
USAGE
}

die() { echo "${SELF}: $*" >&2; exit 2; }

NAME=""
DRY=""
YES=""
FRESH_GIT=""

while [ $# -gt 0 ]; do
  case "$1" in
    -y|--yes)      YES=1; shift ;;
    -n|--dry-run)  DRY=1; shift ;;
    --fresh-git)   FRESH_GIT=1; shift ;;
    -h|--help)     usage; exit 0 ;;
    -*)            die "unknown option '$1'" ;;
    *)             [ -z "${NAME}" ] || die "one name only (got '${NAME}' and '$1')"
                   NAME="$1"; shift ;;
  esac
done

[ -n "${NAME}" ] || { usage; exit 2; }

# Validate against the STRICTEST of the three consumers. Docker image and volume
# names are permissive; a Compose project name must match [a-z0-9][a-z0-9_-]*.
# Sticking to lowercase-alphanumeric-hyphen keeps all three happy, and keeps the
# name safe to drop into a sed expression unescaped further down.
echo "${NAME}" | grep -qE '^[a-z0-9][a-z0-9-]*$' \
  || die "invalid name '${NAME}' — use lowercase letters, digits and hyphens, starting with a letter or digit"

# --fresh-git is checked HERE, before anything is written, because the failure it
# guards against is unrecoverable: `rm -rf .git` followed by a `git commit` that
# refuses for want of a user identity leaves you with the starter's history
# destroyed AND no commit of your own — on a fresh machine, which is exactly when
# someone clones a starter. Fail before the first byte is touched instead.
GIT_NAME=""
GIT_EMAIL=""
if [ -n "${FRESH_GIT}" ]; then
  command -v git >/dev/null 2>&1 || die "--fresh-git needs git on PATH"
  # Read the identity NOW and re-apply it after `git init`. Resolving it later
  # would be too late: if it came from this repo's LOCAL config, `rm -rf .git`
  # takes it with it, and the new repo is back to having none. Capturing it also
  # covers the global case, where re-applying is simply a harmless no-op.
  GIT_NAME="$(git config user.name 2>/dev/null || true)"
  GIT_EMAIL="$(git config user.email 2>/dev/null || true)"
  if [ -z "${GIT_NAME}" ] || [ -z "${GIT_EMAIL}" ]; then
    die "$(cat <<'MSG'
--fresh-git needs a git identity, and this machine has none configured.
Set one, then re-run:
  git config --global user.name  "Your Name"
  git config --global user.email "you@example.com"
(or drop --fresh-git to keep the starter's history)
MSG
)"
  fi
fi

# The current name is whatever the Compose project says it is, so this script is
# re-runnable as a rename rather than a one-shot init.
CURRENT="$(sed -n 's/^name:[[:space:]]*\([a-z0-9][a-z0-9._-]*\).*/\1/p' docker/docker-compose.dev.yml 2>/dev/null | head -1)"
[ -n "${CURRENT}" ] || CURRENT="devbox"

if [ "${CURRENT}" = "${NAME}" ]; then
  echo "${SELF}: already named '${NAME}' — nothing to do."
  exit 0
fi

# Every text file that mentions the current name. Discovered rather than
# hard-coded, so files added later are picked up too. -I skips binaries.
#
# This script excludes ITSELF, for two independent reasons:
#
#   1. Bash reads a script incrementally from an open descriptor, seeking back to
#      where it finished parsing. Rewriting the file in place mid-run shifts every
#      byte after the edit, and the next read returns the wrong offset — a
#      self-rename would corrupt its own execution partway through.
#   2. Its prose is *about* the starter. "generated from the devbox starter" is a
#      statement of provenance and stays true after you rename your project.
LIST="$(mktemp)"
trap 'rm -f "${LIST}"' EXIT
grep -rlI --exclude-dir=.git "${CURRENT}" . 2>/dev/null \
  | sed 's|^\./||' | grep -v "^${SELF}$" | sort > "${LIST}" || true

if [ ! -s "${LIST}" ]; then
  die "found no files mentioning '${CURRENT}' — is this a devbox starter checkout?"
fi

echo "Rename '${CURRENT}' -> '${NAME}' in $(wc -l < "${LIST}" | tr -d ' ') files:"
while IFS= read -r f; do
  n="$(grep -cF "${CURRENT}" "$f" || true)"
  printf '  %-32s %s\n' "$f" "${n} line(s)"
done < "${LIST}"
echo
echo "  images:  ${NAME}-runtime, ${NAME}-dev"
echo "  volumes: ${NAME}-home, ${NAME}-data"
echo "  compose project: ${NAME}"

if [ -n "${DRY}" ]; then
  echo
  echo "(dry run — nothing written)"
  exit 0
fi

if [ -z "${YES}" ]; then
  printf '\nProceed? [y/N] '
  read -r reply || reply=""
  case "${reply}" in
    y|Y|yes|YES) ;;
    *) echo "aborted."; exit 1 ;;
  esac
fi

# Plain substring substitution, not a word-boundary regex: `\b` is a GNU sed
# extension and this script runs on the HOST, which may well be a Mac. It is
# equivalent here anyway — the name only ever appears standalone or as the head
# of `<name>-runtime` / `<name>-home`, never inside a longer word.
#
# Write via a temp file and `cat` back rather than `sed -i`, because the -i flag
# takes a mandatory argument on BSD sed and none on GNU. `cat >` also preserves
# the file's mode, so executables stay executable.
TMP="$(mktemp)"
trap 'rm -f "${LIST}" "${TMP}"' EXIT
while IFS= read -r f; do
  sed "s/${CURRENT}/${NAME}/g" "$f" > "${TMP}" && cat "${TMP}" > "$f"
done < "${LIST}"

# The starter's README intro describes the starter, not your project. Replace it
# with a stub, keeping everything from the first '## ' heading down — that part
# documents the container setup and stays useful. Only fires while the heading is
# still the starter's, so a later rename leaves your own prose alone.
if head -1 README.md 2>/dev/null | grep -q '^# Dev environment starter$'; then
  first_section="$(grep -n '^## ' README.md | head -1 | cut -d: -f1)"
  if [ -n "${first_section}" ]; then
    {
      cat <<STUB
# ${NAME}

Containerised development environment for ${NAME}, from the devbox starter.
\`${NAME}-runtime\` is what runs the project in production; \`${NAME}-dev\` is that
same stack plus Claude Code and the tools for working on it.

STUB
      tail -n "+${first_section}" README.md
    } > "${TMP}" && cat "${TMP}" > README.md
    echo "Rewrote README.md's intro for '${NAME}'."
  fi
fi

echo "Renamed."

if [ -n "${FRESH_GIT}" ]; then
  if [ -z "${YES}" ]; then
    printf "Discard the starter's git history and commit '%s' as the first commit? [y/N] " "${NAME}"
    read -r reply || reply=""
    case "${reply}" in y|Y|yes|YES) ;; *) echo "kept existing history."; FRESH_GIT="" ;; esac
  fi
fi

if [ -n "${FRESH_GIT}" ]; then
  rm -rf .git
  git init -q
  git config user.name  "${GIT_NAME}"
  git config user.email "${GIT_EMAIL}"
  git add -A
  git commit -qm "Initial commit — ${NAME}, from the devbox starter"
  echo "Fresh git history: one commit on $(git rev-parse --abbrev-ref HEAD)."
fi

cat <<NEXT

Next:
  docker build -f docker/runtime.Dockerfile -t ${NAME}-runtime .
  docker build -f docker/dev.Dockerfile     -t ${NAME}-dev     .
  ./docker/dev.sh

Then make it yours:
  - requirements.txt ships LangGraph starter deps — replace with your own
  - docker/runtime-entrypoint.sh has a 'YOUR APP GOES HERE' line to point at your module
  - trim toolchain layers you do not need (TeX, Chromium, JVM/Kotlin) from the Dockerfiles
NEXT
