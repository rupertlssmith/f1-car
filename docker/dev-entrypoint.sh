#!/usr/bin/env bash
# Dev-container entrypoint. Resolves a container user matching the host UID/GID
# (so files written to the bind-mounted /work stay host-owned), grants that user
# passwordless sudo, wires HOME/PATH, and makes `.venv/bin/python` work by pointing
# /work/.venv at the baked venv. Then drops privileges and execs the command
# (default: an interactive bash). See plans/dev-container.md.
set -euo pipefail

. /usr/local/lib/docker/_user-setup.sh

# Match the owner of the bind-mounted /work (HOST_UID/HOST_GID override).
uid="$(resolve_uid "$(stat -c '%u' /work 2>/dev/null || echo 1000)")"
gid="$(resolve_gid "$(stat -c '%g' /work 2>/dev/null || echo 1000)")"
ensure_user "${uid}" "${gid}"          # creates the user/group, exports APP_HOME

uname="$(getent passwd "${uid}" | cut -d: -f1)"

# Passwordless sudo — handy for ad-hoc apt-get while developing (the shared helper
# deliberately omits this; the deployment images do not need it).
echo "${uname} ALL=(ALL) NOPASSWD: ALL" > "/etc/sudoers.d/${uname}"
chmod 440 "/etc/sudoers.d/${uname}"

# HOME is dynamic per resolved user; PATH already has /opt/venv/bin first (agent
# image). Prepend the per-user local bin for pip --user installs.
export HOME="${APP_HOME}"
export PATH="${HOME}/.local/bin:${PATH}"

# Best-effort: ensure the working tree and home are writable by the dev user.
# The agent writes its runtime output under /work/runtime (part of this tree).
chown "${uid}:${gid}" /work "${HOME}" 2>/dev/null || true

# Make the documented `.venv/bin/python -m pipeline_lg …` work verbatim: point
# /work/.venv at the baked venv when the tree has no venv of its own.
[ -e /work/.venv ] || ln -s /opt/venv /work/.venv 2>/dev/null || true

# Default to an interactive shell.
if [ $# -eq 0 ]; then
  set -- bash
fi

exec gosu "${uid}:${gid}" "$@"
