# f1-car

A Red Bull F1 car mod for BeamNG.drive. The mod lives in `vehicles/redbull/`
(plus its wheels in `vehicles/common/redbull_wheels/` and its manifest in
`mod_info/redbull/`); it started as a renamed copy of the Carbonworks F4 mod
kept for reference in `vehicles/fr04/`.

## Building the mod

```bash
pip install xxhash                 # already in the dev image
python3 tools/build_mod.py         # -> dist/redbull.zip
```

Copy `dist/redbull.zip` into your BeamNG mods folder
(`%LocalAppData%\BeamNG.drive\<version>\mods\` on Windows) and it appears in the
vehicle selector. The build regenerates the manifest's file hashes; pass
`--update-manifest` to write them back to `mod_info/redbull/info.json` too.

## Dev environment

Containerised development environment for f1-car, from the devbox starter.
`f1-car-runtime` is what runs the project in production; `f1-car-dev` is that
same stack plus Claude Code and the tools for working on it.

## What's in the box

Everything lives under [`docker/`](docker/) as two layered images:

| Image | Built from | Adds |
|-------|-----------|------|
| **runtime** (`f1-car-runtime`) | `debian:bookworm` | The runtime base: Python 3.14 (via `uv`, in `/opt/venv`), the JVM build toolchain (Temurin JDK 21 + Gradle), a pandoc/xelatex render stack, and a headless Chromium. |
| **dev** (`f1-car-dev`) | `f1-car-runtime` | The interactive layer, `FROM` the runtime image: Claude Code, Kotlin dev tools (`kotlinc`/REPL, `ktlint`), and shell conveniences (git, sudo, ripgrep, fd, vim, bash-completion). |

The dev image is what you use day to day; it inherits the whole runtime toolchain
and adds the hands-on tools on top.

Pinned, checksum-verified tool versions (bump them in the `docker/install_*.sh`
scripts):

| Tool | Version | In image |
|------|---------|----------|
| Python | 3.14 | runtime |
| Temurin JDK | 21 (LTS) | runtime |
| Gradle | 9.6.1 | runtime |
| Kotlin (`kotlinc`, REPL) | 2.4.10 | dev |
| ktlint | 1.8.0 | dev |
| Claude Code | latest stable | dev |

## Prerequisites

- Docker (with Compose if you prefer the Compose path)
- A `requirements.txt` at the repo root. The runtime image installs your Python
  dependencies from it (`uv pip install -r requirements.txt`); the sample app
  that provided one was removed, so add your own — an empty file is fine to get
  a build going.

## Build the images

Run from the repo root. The runtime image is the base, so build it **first**:

```bash
docker build -f docker/runtime.Dockerfile -t f1-car-runtime .
docker build -f docker/dev.Dockerfile   -t f1-car-dev   .
```

(`f1-car-runtime` / `f1-car-dev` are placeholder names — rename them to suit your project,
keeping them consistent across the two build commands and `docker/dev.sh` /
`docker/docker-compose.dev.yml`.)

## Start the dev environment

The `docker/dev.sh` helper launches an interactive container. It bind-mounts the
repo to `/work`, matches your host UID/GID so files you create stay yours,
enables 256-colour output, publishes a couple of dev ports, injects `/work/.env`
when it exists, and gives the container user a **persistent home** on the named
`f1-car-home` volume:

```bash
./docker/dev.sh                                    # interactive bash in /work
./docker/dev.sh python --version                   # run one command instead
./docker/dev.sh pytest -q | tee out.log            # no tty allocated when piped
```

Or via Compose (still needs `f1-car-runtime` built first):

```bash
HOST_UID=$(id -u) HOST_GID=$(id -g) \
  docker compose -f docker/docker-compose.dev.yml run --build --rm --service-ports dev
```

`--service-ports` is not optional if you want the ports — `compose run` ignores
the `ports:` block without it.

Inside the container everything is on `PATH` and works against the bind-mounted
tree:

```bash
python --version        # 3.14, from /opt/venv (also symlinked at /work/.venv)
java -version           # Temurin JDK 21
gradle --version
kotlinc -version        # Kotlin REPL: kotlinc
ktlint --version
claude                  # Claude Code — sign in once; it persists in f1-car-home
```

### What persists

`f1-car-home` is the container user's real home, so `--rm` costs you nothing:
Claude Code's login and history, your shell history, and every package-manager
cache (`~/.gradle`, `~/.cache/uv`, `~/.m2`, `~/.npm`) all live there. A fresh
`gradle build` in a new container reuses yesterday's downloads.

### Ports

`DEV_PORTS` is a space-separated list, each entry `PORT` or `HOST:CONTAINER`;
the default is `8000 8080`.

```bash
DEV_PORTS="5173 3000" ./docker/dev.sh     # a Vite app and a backend
DEV_NO_PORTS=1        ./docker/dev.sh     # nothing published — a second shell
```

Whatever you publish must bind `0.0.0.0` **inside** the container, or the
mapping is dead and the browser says connection refused. Most dev servers
default to loopback and need telling.

Several containers can run side by side; they share one home volume (so one
Claude login) and differ only in which host ports they hold. Full reference,
including a symptom-to-cause table for when it does not come up:
[`docker/README.md`](docker/README.md).

## Run it like production

`docker/run.sh` is the counterpart to `dev.sh`: it runs the **runtime** image
over its own state volume, with nothing from your working tree shadowing what is
baked in. That is the whole reason for two images — you develop against the
exact stack that ships.

```bash
./docker/run.sh                     # then open http://localhost:8080
RUN_DETACH=1 ./docker/run.sh        # background, restarts unless stopped
```

Knobs (`RUN_VOLUME`, `RUN_PORTS`, `RUN_DETACH`, `ENV_FILE`) are documented in
[`docker/README.md`](docker/README.md).

## Make it yours

- **Add your app.** Drop your project back into the repo. Adjust
  `docker/runtime.Dockerfile` (the `COPY`'d source and `WORKDIR`) and
  `docker/runtime-entrypoint.sh` (whose commented `exec` line is where your app goes) to point
  at your own entrypoint, or ignore the runtime entrypoint entirely and just use
  the dev shell.
- **Trim the toolchain.** Don't need the JVM/Kotlin side, or the pandoc/xelatex
  and Chromium stack? Remove the corresponding layers and `install_*.sh` scripts
  to slim the images down.
- **Bump versions.** Each tool is pinned with a checksum in its
  `docker/install_*.sh` script; change the version and matching SHA together.

See [`docker/README.md`](docker/README.md) for a file-by-file reference of the
container setup, the entrypoints, and how volumes and user resolution work.
