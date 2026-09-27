#!/usr/bin/env bash
# Agent entrypoint: resolve a non-root user that matches the runtime volume's
# owner, make the volume writable, then serve a placeholder web page as that user.
#
# By default this runs a simple Python web server on port 8080 (a starter stand-in).
# To run your own LangGraph app instead, comment out the web-server line at the
# bottom and re-enable the `python -m pipeline_lg` line, pointing it at your module.
# pipeline_lg would write each run's state to $PIPELINE_RUNTIME_BASE/<label>
# (the mounted volume, e.g. /runtime/langgraph).
set -euo pipefail
# shellcheck source=/usr/local/lib/docker/_user-setup.sh
source /usr/local/lib/docker/_user-setup.sh

# The mounted volume (base under which pipeline_lg creates <label> run dirs).
: "${PIPELINE_RUNTIME_BASE:=/runtime}"
VOL="${PIPELINE_RUNTIME_BASE}"

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

# Make the volume writable for the resolved user (top-level chown only — pipeline_lg
# and the drivers create the <label>/stages/... subtree on demand, owned by them).
mkdir -p "${VOL}"
chown "${uid}:${gid}" "${VOL}" 2>/dev/null || true

# Secrets arrive as environment variables (--env-file / -e); config.load_env is a
# no-op when /app/.env is absent, so nothing secret needs to be in the image.

# Default: serve the placeholder page on 0.0.0.0:8080. Publish the port to reach
# it from the host, e.g. `docker run -p 8080:8080 tk-agent`.
exec gosu "${uid}:${gid}" python -m http.server 8080 --directory /app/docker/webroot

# App entrypoint (disabled by default) — re-enable and remove the web server above
# to run your LangGraph app instead:
# exec gosu "${uid}:${gid}" python -m pipeline_lg "$@"
