# Dev environment starter

A quick-start template for spinning up a containerised development environment
with a broad, version-pinned toolchain already wired together. Clone it, build
two images, and drop into an interactive shell that has Python, a JVM/Kotlin
build stack, and Claude Code ready to go — all against your repo bind-mounted at
`/work`.

This repo is deliberately domain-agnostic. It previously hosted a Python +
LangGraph project; that has been cleared out, leaving the reusable `docker/`
setup as the starting point for your own work.

## What's in the box

Everything lives under [`docker/`](docker/) as two layered images:

| Image | Built from | Adds |
|-------|-----------|------|
| **agent** (`tk-agent`) | `debian:bookworm` | The runtime base: Python 3.14 (via `uv`, in `/opt/venv`), the JVM build toolchain (Temurin JDK 21 + Gradle), a pandoc/xelatex render stack, and a headless Chromium. |
| **dev** (`tk-dev`) | `tk-agent` | The interactive layer, `FROM` the agent image: Claude Code, Kotlin dev tools (`kotlinc`/REPL, `ktlint`), and shell conveniences (git, sudo, ripgrep, fd, vim, bash-completion). |

The dev image is what you use day to day; it inherits the whole agent toolchain
and adds the hands-on tools on top.

Pinned, checksum-verified tool versions (bump them in the `docker/install_*.sh`
scripts):

| Tool | Version | In image |
|------|---------|----------|
| Python | 3.14 | agent |
| Temurin JDK | 21 (LTS) | agent |
| Gradle | 9.6.1 | agent |
| Kotlin (`kotlinc`, REPL) | 2.4.10 | dev |
| ktlint | 1.8.0 | dev |
| Claude Code | latest stable | dev |

## Prerequisites

- Docker (with Compose if you prefer the Compose path)
- A `requirements.txt` at the repo root. The agent image installs your Python
  dependencies from it (`uv pip install -r requirements.txt`); the sample app
  that provided one was removed, so add your own — an empty file is fine to get
  a build going.

## Build the images

Run from the repo root. The agent image is the base, so build it **first**:

```bash
docker build -f docker/agent.Dockerfile -t tk-agent .
docker build -f docker/dev.Dockerfile   -t tk-dev   .
```

(`tk-agent` / `tk-dev` are placeholder names — rename them to suit your project,
keeping them consistent across the two build commands and `docker/dev.sh` /
`docker/docker-compose.dev.yml`.)

## Start the dev environment

The `docker/dev.sh` helper launches an interactive container. It bind-mounts the
repo to `/work`, matches your host UID/GID so files you create stay yours,
enables 256-colour output, and persists Claude Code's login and your shell
history in a named `tk-home` volume:

```bash
./docker/dev.sh                                    # interactive bash in /work
./docker/dev.sh python --version                   # run one command instead
```

Or via Compose (still needs `tk-agent` built first):

```bash
HOST_UID=$(id -u) HOST_GID=$(id -g) \
  docker compose -f docker/docker-compose.dev.yml run --build --rm dev
```

Inside the container everything is on `PATH` and works against the bind-mounted
tree:

```bash
python --version        # 3.14, from /opt/venv (also symlinked at /work/.venv)
java -version           # Temurin JDK 21
gradle --version
kotlinc -version        # Kotlin REPL: kotlinc
ktlint --version
claude                  # Claude Code — sign in once; it persists in tk-home
```

## Make it yours

- **Add your app.** Drop your project back into the repo. Adjust
  `docker/agent.Dockerfile` (the `COPY`'d source and `WORKDIR`) and
  `docker/agent-entrypoint.sh` (which runs `python -m pipeline_lg "$@"`) to point
  at your own entrypoint, or ignore the agent entrypoint entirely and just use
  the dev shell.
- **Trim the toolchain.** Don't need the JVM/Kotlin side, or the pandoc/xelatex
  and Chromium stack? Remove the corresponding layers and `install_*.sh` scripts
  to slim the images down.
- **Bump versions.** Each tool is pinned with a checksum in its
  `docker/install_*.sh` script; change the version and matching SHA together.

See [`docker/README.md`](docker/README.md) for a file-by-file reference of the
container setup, the entrypoints, and how volumes and user resolution work.
