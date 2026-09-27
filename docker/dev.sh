#!/usr/bin/env bash
# Launch the interactive dev container (tk-dev).
#
# Binds the repo working tree to /work, persists the dev home (Claude Code login,
# shell history) in the tk-home volume, enables 256-colour output, and matches the
# host UID/GID. Secrets come from /work/.env, which pipeline_lg reads itself.
#
# The agent writes its runtime output to /work/runtime (the bind mount, visible on
# the host) — there is no runtime volume. The only named volume is tk-home.
#
# No args  -> interactive bash (then run `claude`, `python -m pipeline_lg …`).
# With args -> run that command in the container instead.
#   ./docker/dev.sh
#   ./docker/dev.sh python -m pipeline_lg run --label langgraph
#
# Equivalent to `docker compose -f docker/docker-compose.dev.yml run --rm dev`.
#
# Build first (the agent image is the base):
#   docker build -f docker/agent.Dockerfile -t tk-agent .
#   docker build -f docker/dev.Dockerfile   -t tk-dev   .
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE="${DEV_IMAGE:-tk-dev}"
HOME_VOLUME="${DEV_HOME_VOLUME:-tk-home}"

docker volume create "${HOME_VOLUME}" >/dev/null

exec docker run -it --rm \
  -e TERM=xterm-256color \
  -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
  -v "$PWD":/work \
  -v "${HOME_VOLUME}":/home/dev \
  "${IMAGE}" "$@"
