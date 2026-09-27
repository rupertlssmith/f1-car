#!/usr/bin/env bash
# Shared entrypoint helpers — sourced by runtime-entrypoint.sh and dev-entrypoint.sh.
#
# Borrowed from eco-compiler/docker/eco-dev-entrypoint.sh: resolve a target
# UID/GID at runtime and create a matching ordinary (non-root) user, so files the
# container writes are owned by the invoking host user rather than root. We drop
# privileges to that user with `gosu` in each entrypoint.
#
# Unlike eco's version there is no serena/MCP/Claude setup and no passwordless
# sudo — neither image needs them.
set -euo pipefail

DEFAULT_USER="app"

# resolve_uid <fallback> — HOST_UID wins, else the fallback.
resolve_uid() { echo "${HOST_UID:-${1:-1000}}"; }
resolve_gid() { echo "${HOST_GID:-${1:-1000}}"; }

# ensure_user <uid> <gid> — create the group/user if absent; export APP_HOME.
ensure_user() {
  local uid="$1" gid="$2"
  if ! getent group "${gid}" >/dev/null 2>&1; then
    groupadd -g "${gid}" "${DEFAULT_USER}" 2>/dev/null || groupadd -g "${gid}" "grp${gid}"
  fi
  local gname; gname="$(getent group "${gid}" | cut -d: -f1)"
  if ! getent passwd "${uid}" >/dev/null 2>&1; then
    useradd -m -u "${uid}" -g "${gname}" -s /bin/bash "${DEFAULT_USER}" 2>/dev/null \
      || useradd -m -u "${uid}" -g "${gid}" -s /bin/bash "user${uid}"
  fi
  APP_HOME="$(getent passwd "${uid}" | cut -d: -f6)"
  mkdir -p "${APP_HOME}"
  chown "${uid}:${gid}" "${APP_HOME}" 2>/dev/null || true
  export APP_HOME
}
