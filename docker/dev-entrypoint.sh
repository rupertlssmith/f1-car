#!/usr/bin/env bash
# Dev-container entrypoint. Resolves a container user matching the host UID/GID
# (so files written to the bind-mounted /work stay host-owned), puts that user's
# HOME on the volume dev.sh mounted, grants passwordless sudo, wires HOME/PATH,
# and makes `.venv/bin/python` work by pointing /work/.venv at the baked venv.
# Then drops privileges and execs the command (default: an interactive bash).
set -euo pipefail

. /usr/local/lib/docker/_user-setup.sh

# Match the owner of the bind-mounted /work (HOST_UID/HOST_GID override).
uid="$(resolve_uid "$(stat -c '%u' /work 2>/dev/null || echo 1000)")"
gid="$(resolve_gid "$(stat -c '%g' /work 2>/dev/null || echo 1000)")"
ensure_user "${uid}" "${gid}"          # creates the user/group, exports APP_HOME

uname="$(getent passwd "${uid}" | cut -d: -f1)"

# Passwordless sudo — handy for ad-hoc apt-get while developing (the shared helper
# deliberately omits this; the runtime image does not need it).
echo "${uname} ALL=(ALL) NOPASSWD: ALL" > "/etc/sudoers.d/${uname}"
chmod 440 "/etc/sudoers.d/${uname}"

# ---------------------------------------------------------------- the home
# Put HOME on the volume dev.sh mounts (DEV_HOME), rather than hoping the two
# agree by coincidence. They did not: `_user-setup.sh` is shared with the runtime
# image, where DEFAULT_USER is "app", so `useradd -m` gives the resolved user
# /home/app — while dev.sh mounts its named home volume at /home/dev, a path
# nothing else referred to. The result looked like a persistent home and was not
# one: $HOME sat on the container's overlay and dev.sh runs --rm, so every
# `claude` login, every shell history line and every package-manager cache
# (~/.gradle, ~/.cache/uv, ~/.npm) was discarded the moment you exited.
#
# Renaming DEFAULT_USER would fix the dev image by breaking the runtime one, and
# would still break for a host UID that falls through to the `user${uid}`
# fallback. So the mount path is authoritative instead: whatever dev.sh mounted
# becomes the user's home.
if [ -n "${DEV_HOME:-}" ] && [ "${DEV_HOME}" != "${APP_HOME}" ]; then
  usermod -d "${DEV_HOME}" "${uname}"
  mkdir -p "${DEV_HOME}"
  # A freshly created named volume is empty and root-owned, so seed the skeleton
  # that `useradd -m` would have written had the home been created after the
  # mount. Only on first run — never over existing content.
  if [ -z "$(ls -A "${DEV_HOME}" 2>/dev/null)" ]; then
    cp -a /etc/skel/. "${DEV_HOME}/" 2>/dev/null || true
    chown -R "${uid}:${gid}" "${DEV_HOME}" 2>/dev/null || true
  fi
  APP_HOME="${DEV_HOME}"
fi

# HOME is dynamic per resolved user; PATH already has /opt/venv/bin first (runtime
# image). Prepend the per-user local bin for pip --user installs.
export HOME="${APP_HOME}"
export PATH="${HOME}/.local/bin:${PATH}"

# Best-effort: ensure the working tree and home are writable by the dev user.
# TOP LEVEL ONLY, deliberately — a home volume accumulates package caches and
# model downloads, and `chown -R` over gigabytes on every container start would
# be absurd. The skel seed above is the one recursive case, and it runs against
# an empty volume.
chown "${uid}:${gid}" /work "${HOME}" 2>/dev/null || true

# Say so HERE if the home is still not writable. Otherwise the symptom is
# `claude` failing to save its login, or pip/gradle failing to write a cache,
# several minutes later and reported as a path rather than a cause.
if ! gosu "${uid}:${gid}" test -w "${HOME}"; then
  {
    echo "dev-entrypoint: uid ${uid}:${gid} cannot write HOME (${HOME}, owned by $(stat -c '%u:%g' "${HOME}"))."
    echo "  Nothing will persist — logins, history and caches all live there."
    echo "  Usually a home volume populated under a different UID. Fix it once:"
    echo "    docker run --rm -v ${DEV_HOME_VOLUME:-devbox-home}:/h busybox chown -R ${uid}:${gid} /h"
  } >&2
fi

# The same guarantee the runtime entrypoint makes: $APP_RUNTIME_DIR exists and is
# writable before your code starts, so code that reads it works identically here
# and under docker/run.sh. The dev image points it into the bind-mounted tree.
if [ -n "${APP_RUNTIME_DIR:-}" ]; then
  mkdir -p "${APP_RUNTIME_DIR}" 2>/dev/null || true
  chown "${uid}:${gid}" "${APP_RUNTIME_DIR}" 2>/dev/null || true
fi

# Make the documented `.venv/bin/python …` work verbatim: point /work/.venv at
# the baked venv when the tree has no venv of its own.
[ -e /work/.venv ] || ln -s /opt/venv /work/.venv 2>/dev/null || true

# Default to an interactive shell.
if [ $# -eq 0 ]; then
  set -- bash
fi

exec gosu "${uid}:${gid}" "$@"
