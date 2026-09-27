#!/usr/bin/env bash
# Runtime entrypoint: resolve a non-root user that matches the runtime volume's
# owner, make the volume writable, then run the project as that user.
#
# By default it serves a placeholder web page on port 8080 — a stand-in so the
# image does something visible before you have an app. To run yours, comment out
# the web-server line at the bottom and re-enable the one below it, pointing it
# at your own module. It should write its state under $APP_RUNTIME_DIR (the
# mounted volume, /runtime by default), which this script prepares for it.
set -euo pipefail
# shellcheck source=/usr/local/lib/docker/_user-setup.sh
source /usr/local/lib/docker/_user-setup.sh

# The mounted volume — where the project keeps state that outlives the container.
: "${APP_RUNTIME_DIR:=/runtime}"
VOL="${APP_RUNTIME_DIR}"

uid="$(resolve_uid 1000)"
gid="$(resolve_gid 1000)"

# With no explicit HOST_UID, adopt the volume's current owner so newly written
# files match whoever populated it (e.g. a host bind-mount). A pristine, still
# root-owned volume falls back to 1000 and gets chowned below.
if [[ -z "${HOST_UID:-}" && -d "${VOL}" ]]; then
  vuid="$(stat -c '%u' "${VOL}")"
  vgid="$(stat -c '%g' "${VOL}")"
  if [[ "${vuid}" != "0" ]]; then uid="${vuid}"; gid="${vgid}"; fi
fi

ensure_user "${uid}" "${gid}"
export HOME="${APP_HOME}"

# Make the volume writable for the resolved user. TOP LEVEL ONLY: your app
# creates its own subtree beneath, owned by whoever ran it, and a restored
# snapshot can be large enough that `chown -R` on every start is absurd.
mkdir -p "${VOL}"
chown "${uid}:${gid}" "${VOL}" 2>/dev/null || true

# Secrets arrive as environment variables (--env-file / -e), so nothing secret
# needs to be baked into the image.

# Default: serve the placeholder page on 0.0.0.0:8080. Publish the port to reach
# it from the host, e.g. `docker run -p 8080:8080 devbox-runtime`.
exec gosu "${uid}:${gid}" python -m http.server 8080 --directory /app/docker/webroot

# YOUR APP GOES HERE — delete the web-server line above and uncomment this one,
# naming your own module. `"$@"` forwards whatever was passed to the container,
# so `./docker/run.sh --flag` reaches your CLI:
# exec gosu "${uid}:${gid}" python -m your_app "$@"
