# docker/

Container setup for this dev-environment starter (see the [top-level
README](../README.md) for the overview). The interactive **dev** image is what
you run day to day; it is built `FROM` the runtime image, which packages the full
runtime toolchain. `f1-car-runtime` / `f1-car-dev` are placeholder image names —
rename to suit your project.

| File | Purpose |
|------|---------|
| `runtime.Dockerfile` | **The** image — what runs the project in production: Python 3.14 in `/opt/venv`, the JVM build toolchain (Temurin JDK 21 + Gradle), pandoc/xelatex, headless Chromium. Base image for the dev image. Installs Python deps from `requirements.txt` at the repo root. |
| `runtime-entrypoint.sh` | Resolve a non-root user, prepare the runtime dir, then (by default) serve a placeholder page with `python -m http.server 8080`. Swap in `python -m your_app "$@"` to run your own app — the line is present but commented out. |
| `run.sh` | Run the **runtime** image as production would: state volume, `RUN_PORTS`, `.env`, `RUN_DETACH=1` for a background service. The counterpart to `dev.sh`. |
| `webroot/index.html` | The placeholder page served on port 8080 by the default runtime entrypoint. |
| `dev.Dockerfile` | Interactive **dev** environment — the runtime + Claude Code + dev conveniences + Kotlin dev tools, `FROM` the runtime image. Not for deployment. |
| `dev-entrypoint.sh` | Resolve a host-matching user, put its `HOME` on the mounted volume, grant sudo, wire `HOME`/`PATH`, symlink `/work/.venv`→`/opt/venv`, `exec bash`. |
| `dev.sh` | Launch the dev container: bind repo→`/work`, `f1-car-home` volume, publish `DEV_PORTS`, inject `.env`, 256-colour. |
| `docker-compose.dev.yml` | Dev service + the `f1-car-home` volume (Compose alternative to `dev.sh`). |
| `install_claude.sh` | Vendored Claude Code installer (checksum-verified standalone binary). |
| `install_jvm.sh` | Pinned, checksum-verified JVM build toolchain — Temurin JDK 21 (LTS) → `/opt/java/current` and Gradle → `/opt/gradle/current`. Used by the **runtime** image. |
| `install_kotlin.sh` | Pinned, checksum-verified Kotlin dev tools — `kotlinc`/REPL and `ktlint` → `/opt/kotlin`. Used by the **dev** image. |
| `_user-setup.sh` | Shared UID/GID + user-creation helpers. |

**Volumes:** the only named volume is `f1-car-home`, mounted at `/home/dev`. The
repo is bind-mounted at `/work` and anything written under it is visible on the
host, so there is no runtime volume.

## Interactive dev container

The runtime + Claude Code in one shell. `dev.Dockerfile` builds `FROM` the
runtime image, so build that base **first**:

```bash
# 1. Build the runtime base image, then the dev image on top of it.
docker build -f docker/runtime.Dockerfile -t f1-car-runtime .
docker build -f docker/dev.Dockerfile   -t f1-car-dev   .

# 2. Launch an interactive shell (binds the repo to /work).
./docker/dev.sh

# Inside the container, everything runs against the bind-mounted tree:
#   claude
#   python --version   # 3.14, from /opt/venv (symlinked at /work/.venv)
#   kotlinc -version   java -version   gradle --version
```

`./docker/dev.sh <cmd>` runs `<cmd>` instead of dropping to a shell. A tty is
allocated only when there is one at both ends, so `./docker/dev.sh pytest | tee
out.log` pipes cleanly and the same script works unattended in CI.

Building the runtime image needs a `requirements.txt` at the repo root — it is the
Python dependency list `runtime.Dockerfile` installs. A basic LangGraph starter one
is included; edit or replace it with your project's deps.

### The home volume — what persists, and why it must

`f1-car-home` is mounted at `/home/dev`, and `dev.sh` passes that same path as
`DEV_HOME` so the entrypoint makes it the resolved user's actual home. That one
wiring decides whether **anything** survives `--rm`:

- Claude Code's login and history (`~/.claude`) — sign in once, not once a day
- shell history
- package-manager caches: `~/.gradle`, `~/.cache/uv`, `~/.m2`, `~/.npm`

It is worth stating because the obvious-looking setup is broken and looks fine.
`_user-setup.sh` is shared with the runtime image, where `DEFAULT_USER` is `app`,
so `useradd -m` hands the resolved user `/home/app` — while the volume mounts at
`/home/dev`. Mount one path and set `HOME` to another and you get a volume that
is genuinely persistent and genuinely unused: `$HOME` sits on the container
overlay, `dev.sh` runs `--rm`, and every login and cache goes with it. Hence
`DEV_HOME`: the mount path is authoritative, and the entrypoint `usermod -d`s
the user onto it (seeding `/etc/skel` on a first, empty volume).

Give an instance its own home with `DEV_HOME_VOLUME=other-home ./docker/dev.sh`.

### Ports

`dev.sh` publishes `DEV_PORTS` — a space-separated list, each entry either
`PORT` or `HOST:CONTAINER`. The default is `8000 8080`.

```bash
DEV_PORTS="5173 3000" ./docker/dev.sh     # a Vite app and a backend
DEV_PORTS="8081:8080" ./docker/dev.sh     # container 8080 -> host 8081
DEV_NO_PORTS=1        ./docker/dev.sh     # publish nothing
```

Anything you publish **must bind `0.0.0.0` inside the container** or the mapping
is dead: Docker forwards a published port to the container's external interface,
so a server listening on `127.0.0.1` inside is unreachable from the host — and
the symptom is "connection refused" from a browser, which reads like a broken
port mapping rather than a server on the wrong interface. Most dev servers
default to loopback, so pass their `--host 0.0.0.0` equivalent.

### Environment / secrets

`/work/.env` is passed with `--env-file` when it exists, so `ANTHROPIC_API_KEY`
and friends reach what you run without being baked into the image. Point
elsewhere with `ENV_FILE=other.env`, or skip it with `ENV_FILE=`.

### Running several at once

Only one container can hold a given host port, so a second shell alongside a
running one wants its own ports or none:

```bash
DEV_NO_PORTS=1 ./docker/dev.sh                  # extra shell, publishes nothing
DEV_PORTS="8001 8081" ./docker/dev.sh           # or its own
```

Nothing else stops them coexisting. They share `f1-car-home` by default, so one
Claude Code login and one shell history serve all of them.

### The Compose path

```bash
docker build -f docker/runtime.Dockerfile -t f1-car-runtime .
HOST_UID=$(id -u) HOST_GID=$(id -g) \
  docker compose -f docker/docker-compose.dev.yml run --build --rm --service-ports dev
```

`--service-ports` is not optional if you want the ports: `compose run` ignores
the `ports:` block without it. The two paths are kept interchangeable on purpose
— same image, same `f1-car-home` volume, same `DEV_HOME` — so edit both when you
change one.

### When it does not come up

| Symptom | Cause |
|---|---|
| `claude` asks you to log in again every session | `$HOME` is not on the volume. Check `echo $HOME` inside — it must match the mount (`/home/dev`). An older `dev.sh` that does not pass `DEV_HOME` is the usual reason. |
| Compose asks you to log in although `dev.sh` did not | Two different volumes. Compose prefixes a volume with the project name unless it is pinned with an explicit `name:` — `docker volume ls` will show both `f1-car-home` and something like `docker_f1-car-home`. |
| Browser says connection refused, container looks healthy | The server bound `127.0.0.1` inside. Pass `--host 0.0.0.0` (or the equivalent). |
| Nothing published at all under Compose | `compose run` without `--service-ports`. |
| `docker: Error ... port is already allocated` | Another instance holds it. `DEV_NO_PORTS=1` or give this one its own `DEV_PORTS`. |
| Piped output full of `^M`, or a hang in CI | Fixed: `dev.sh` only allocates a tty when stdin *and* stdout are ttys. If you invoke `docker run` by hand, drop `-t`. |
| Gradle/uv re-download everything on each start | The home volume is not writable — the entrypoint prints the `chown` one-liner that fixes it. |
| Files created in `/work` are owned by root on the host | `HOST_UID`/`HOST_GID` did not reach the container. `dev.sh` passes them; Compose needs them in your environment. |
| Edits appear to be ignored by a build | An inherited "use the baked artifact" env var from the runtime image. See the ENV AUDIT block in `dev.Dockerfile`. |

## Running the runtime image

`docker/run.sh` is to the runtime image what `dev.sh` is to the dev image, and
the difference between them is the point of having two images: `dev.sh` mounts
your working tree over `/work` so edits are live, while `run.sh` runs what is
baked in, with nothing from your tree shadowing it. If it works under `run.sh`
it works deployed.

```bash
docker build -f docker/runtime.Dockerfile -t f1-car-runtime .

./docker/run.sh                     # then open http://localhost:8080
RUN_DETACH=1 ./docker/run.sh        # background, restarts unless stopped
./docker/run.sh --some-flag         # args pass through to the entrypoint
```

| Variable | Default | Purpose |
|---|---|---|
| `RUN_IMAGE` | `f1-car-runtime` | Image to run. |
| `RUN_VOLUME` | `f1-car-data` | Mounted at `/runtime` (where `APP_RUNTIME_DIR` points), so state survives `--rm`. A path (`./state`) bind-mounts onto the host instead; empty mounts nothing. |
| `RUN_PORTS` | `8080` | Same syntax as `DEV_PORTS`. `RUN_NO_PORTS=1` publishes nothing. |
| `ENV_FILE` | `.env` | Passed with `--env-file` when the file exists. |
| `RUN_DETACH` | — | `-d --restart unless-stopped` instead of an attached run. |
| `RUN_HOST_UID` | auto | Force the `HOST_UID`/`HOST_GID` pass-through on (`1`) or off (`0`). |

**On `HOST_UID`.** `run.sh` passes it only when the state is a bind mount, where
files land on the host and want to be yours. For a named volume it is left off
deliberately: nothing outside a container touches those files, and forcing your
login uid means a by-hand run resolves to a *different* user than an unattended
one (which passes no `HOST_UID` and adopts the volume's existing owner) — so it
would fail to write the very tree those runs created.

By default the entrypoint serves the `webroot/index.html` placeholder on 8080.
To run a real app, re-enable the commented `exec` line at the bottom of
`runtime-entrypoint.sh` and point it at your module.
