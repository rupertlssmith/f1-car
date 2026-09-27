#!/usr/bin/env bash
# Launch the interactive dev container (f1-car-dev).
#
# Binds the repo working tree to /work, persists the dev home (Claude Code login,
# shell history, package caches) in the f1-car-home volume, enables 256-colour
# output, matches the host UID/GID, injects /work/.env if present, and publishes
# a couple of common dev ports.
#
# No args  -> interactive bash (then run `claude`, `python`, `gradle`, …).
# With args -> run that command in the container instead.
#   ./docker/dev.sh
#   ./docker/dev.sh python --version
#   ./docker/dev.sh pytest -q | tee test.log     # no tty is allocated when piped
#
# Equivalent to `docker compose -f docker/docker-compose.dev.yml run --rm dev`.
#
# Build first (the runtime image is the base):
#   docker build -f docker/runtime.Dockerfile -t f1-car-runtime .
#   docker build -f docker/dev.Dockerfile   -t f1-car-dev   .
#
# ---------------------------------------------------------------------------
# PORTS. DEV_PORTS is a space-separated list, each entry either `PORT` (published
# on the same host port) or `HOST:CONTAINER`:
#
#   DEV_PORTS="5173 3000" ./docker/dev.sh          # a Vite app and a backend
#   DEV_PORTS="8081:8080" ./docker/dev.sh          # container 8080 -> host 8081
#   DEV_NO_PORTS=1        ./docker/dev.sh          # publish nothing
#
# Whatever you publish must bind 0.0.0.0 *inside* the container or the mapping is
# dead: Docker forwards a published port to the container's external interface,
# so a server listening on 127.0.0.1 inside is unreachable from the host and the
# mapping looks broken. Most dev servers default to loopback — pass their
# --host 0.0.0.0 equivalent.
#
# PARALLEL INSTANCES. Only one container can hold a given host port, so a second
# shell alongside a running one wants `DEV_NO_PORTS=1` (or its own DEV_PORTS).
# Nothing else stops them coexisting: they share the f1-car-home volume by
# default, so one Claude Code login and one shell history serve all of them.
# Give an instance its own home with DEV_HOME_VOLUME=other-home.
#
# ENV. /work/.env is passed with --env-file when it exists, so secrets
# (ANTHROPIC_API_KEY, …) reach whatever you run without being baked into the
# image. Set ENV_FILE to point elsewhere, or ENV_FILE= to skip it.
# ---------------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE="${DEV_IMAGE:-f1-car-dev}"
HOME_VOLUME="${DEV_HOME_VOLUME:-f1-car-home}"
# Where that volume mounts AND the home the entrypoint gives the resolved user —
# passed through as DEV_HOME so the two cannot drift apart. They previously did:
# the volume mounted here while the user's home was /home/app on the container
# overlay, so nothing in $HOME survived --rm. See docker/dev-entrypoint.sh.
HOME_DIR="${DEV_HOME_DIR:-/home/dev}"
ENV_FILE="${ENV_FILE-.env}"

args=(--rm)

# A tty only when there is one on BOTH ends: `-t` against a pipe mangles output
# with carriage returns, which is what `./docker/dev.sh pytest | tee` would get.
# `-i` is unconditional so stdin can still be piped in.
if [ -t 0 ] && [ -t 1 ]; then
  args+=(-it)
else
  args+=(-i)
fi

# Ports: default to two common dev-server ports, overridable per instance.
DEV_PORTS="${DEV_PORTS-8000 8080}"
# An `x && y` one-liner here would be a `set -e` landmine: when DEV_NO_PORTS is
# unset the test fails, the compound returns non-zero, and the script exits.
if [ -n "${DEV_NO_PORTS:-}" ]; then
  DEV_PORTS=
fi
for p in ${DEV_PORTS}; do
  case "$p" in
    *:*) args+=(-p "$p") ;;
    *)   args+=(-p "$p:$p") ;;
  esac
done

# Secrets, when the file is there. Absent is the normal case for a fresh clone.
if [ -n "${ENV_FILE}" ] && [ -f "${ENV_FILE}" ]; then
  args+=(--env-file "${ENV_FILE}")
fi

docker volume create "${HOME_VOLUME}" >/dev/null

exec docker run "${args[@]}" \
  -e TERM=xterm-256color \
  -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
  -e DEV_HOME="${HOME_DIR}" \
  -e DEV_HOME_VOLUME="${HOME_VOLUME}" \
  -v "$PWD":/work \
  -v "${HOME_VOLUME}":"${HOME_DIR}" \
  "${IMAGE}" "$@"
