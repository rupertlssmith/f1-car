#!/usr/bin/env bash
# Run the project — the RUNTIME image (f1-car-runtime), as production would.
#
# The counterpart to docker/dev.sh: same conventions, opposite purpose. dev.sh
# gives you a shell in the dev image over a bind-mounted working tree; this runs
# the runtime image over its own state volume, with nothing from your tree
# shadowing what is baked in. If it works here it works deployed.
#
#   ./docker/run.sh                       # whatever the entrypoint defaults to
#   ./docker/run.sh --some-flag           # args pass through to the entrypoint
#   RUN_DETACH=1 ./docker/run.sh          # background, restarts unless stopped
#
# Build first:
#   docker build -f docker/runtime.Dockerfile -t f1-car-runtime .
#
# ---------------------------------------------------------------------------
# STATE. RUN_VOLUME (default f1-car-data) is mounted at /runtime, which is what
# the image's APP_RUNTIME_DIR points at, so state survives --rm. Set
# RUN_VOLUME= to run with no volume at all, or give it a host path to write onto
# the host filesystem instead:
#
#   RUN_VOLUME=./state ./docker/run.sh
#
# PORTS. RUN_PORTS, same syntax as dev.sh's DEV_PORTS: space-separated, each
# entry `PORT` or `HOST:CONTAINER`. Default 8080 (what the placeholder
# entrypoint serves). RUN_NO_PORTS=1 publishes nothing.
#
# The same trap applies as in dev.sh: a server bound to 127.0.0.1 inside the
# container is unreachable from the host however you map the port.
#
# ENV. /work/.env is passed with --env-file when present, so secrets reach the
# process without being baked into the image. ENV_FILE overrides, ENV_FILE=
# skips.
# ---------------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE="${RUN_IMAGE:-f1-car-runtime}"
VOLUME="${RUN_VOLUME-f1-car-data}"
ENV_FILE="${ENV_FILE-.env}"

args=(--rm)

# Detached is the deployment shape; interactive is the "does it work" shape.
if [ -n "${RUN_DETACH:-}" ]; then
  args=(-d --restart unless-stopped)          # NB: not --rm, it must survive
elif [ -t 0 ] && [ -t 1 ]; then
  args+=(-it)
else
  args+=(-i)
fi

RUN_PORTS="${RUN_PORTS-8080}"
if [ -n "${RUN_NO_PORTS:-}" ]; then
  RUN_PORTS=
fi
for p in ${RUN_PORTS}; do
  case "$p" in
    *:*) args+=(-p "$p") ;;
    *)   args+=(-p "$p:$p") ;;
  esac
done

# HOST_UID is passed only when it can do any good — i.e. when the state lives on
# a BIND MOUNT, where the files land on the host filesystem and want to be owned
# by you. For a named volume nothing outside a container ever touches those
# files, and forcing your login uid actively hurts: an unattended run (cron, a
# compose service) passes no HOST_UID and lets the entrypoint adopt the volume's
# existing owner, so a by-hand run under a different uid resolves to a DIFFERENT
# user than every scheduled one and cannot write the tree they created.
#
# Set RUN_HOST_UID=1 to force it on, 0 to force it off.
case "${VOLUME}" in
  /*|./*|../*) bind_mount=1 ;;                # a path, not a volume name
  *)           bind_mount=0 ;;
esac
if [ "${RUN_HOST_UID:-${bind_mount}}" = "1" ]; then
  args+=(-e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)")
fi

if [ -n "${VOLUME}" ]; then
  case "${VOLUME}" in
    # `docker run -v` demands an ABSOLUTE source path — a relative one is read
    # as a named volume and rejected as an invalid name. (Compose accepts
    # relative paths, which is where the habit comes from.) Resolve it here so
    # `RUN_VOLUME=./state` works the way it obviously reads.
    /*|./*|../*) mkdir -p "${VOLUME}"; VOLUME="$(cd "${VOLUME}" && pwd)" ;;
    *)           docker volume create "${VOLUME}" >/dev/null ;;
  esac
  args+=(-v "${VOLUME}":/runtime)
fi

if [ -n "${ENV_FILE}" ] && [ -f "${ENV_FILE}" ]; then
  args+=(--env-file "${ENV_FILE}")
fi

exec docker run "${args[@]}" "${IMAGE}" "$@"
