# docker/

Container setup for this dev-environment starter (see the [top-level
README](../README.md) for the overview). The interactive **dev** image is what
you run day to day; it is built `FROM` the agent image, which packages the full
runtime toolchain. `tk-agent` / `tk-dev` are placeholder image names — rename to
suit your project.

| File | Purpose |
|------|---------|
| `agent.Dockerfile` | The LangGraph agent runtime (Python + LangGraph/OpenAI + pandoc/xelatex + headless Chromium + JVM build toolchain: Temurin JDK 21 + Gradle). Base image for the dev image. Installs Python deps from `requirements.txt` at the repo root. |
| `agent-entrypoint.sh` | Resolve a non-root user, prepare the runtime dir, then (by default) serve a placeholder page with `python -m http.server 8080`. Swap in `python -m pipeline_lg "$@"` to run your own app — the line is present but commented out. |
| `webroot/index.html` | The placeholder page served on port 8080 by the default agent entrypoint. |
| `dev.Dockerfile` | Interactive **dev** environment — the agent runtime + Claude Code + dev conveniences + Kotlin dev tools, `FROM` the agent image. Not for deployment. |
| `dev-entrypoint.sh` | Resolve a host-matching user, grant sudo, wire `HOME`/`PATH`, symlink `/work/.venv`→`/opt/venv`, `exec bash`. |
| `dev.sh` | Launch the dev container: bind repo→`/work`, `tk-home` volume, 256-colour. |
| `docker-compose.dev.yml` | Dev service + the `tk-home` volume (Compose alternative to `dev.sh`). |
| `install_claude.sh` | Vendored Claude Code installer (checksum-verified standalone binary). |
| `install_jvm.sh` | Pinned, checksum-verified JVM build toolchain — Temurin JDK 21 (LTS) → `/opt/java/current` and Gradle → `/opt/gradle/current`. Used by the **agent** image. |
| `install_kotlin.sh` | Pinned, checksum-verified Kotlin dev tools — `kotlinc`/REPL and `ktlint` → `/opt/kotlin`. Used by the **dev** image. |
| `_user-setup.sh` | Shared UID/GID + user-creation helpers. |

**Volumes:** the only named volume is `tk-home`, which holds `/home/dev` (Claude
Code login + shell history). The repo is bind-mounted at `/work` and the agent
writes its runtime output to `/work/runtime` (visible on the host) — no runtime volume.

## Interactive dev container

The agent runtime + Claude Code in one shell. `dev.Dockerfile` builds `FROM` the
agent image, so build that base **first**:

```bash
# 1. Build the agent base image, then the dev image on top of it.
docker build -f docker/agent.Dockerfile -t tk-agent .
docker build -f docker/dev.Dockerfile   -t tk-dev   .

# 2. Launch an interactive shell (binds the repo to /work).
./docker/dev.sh

# Inside the container, everything runs against the bind-mounted tree:
#   claude
#   python --version   # 3.14, from /opt/venv (symlinked at /work/.venv)
#   kotlinc -version   java -version   gradle --version
```

`./docker/dev.sh <cmd>` runs `<cmd>` instead of dropping to a shell.

Building the agent image needs a `requirements.txt` at the repo root — it is the
Python dependency list `agent.Dockerfile` installs. A basic LangGraph starter one
is included; edit or replace it with your project's deps.

## Running the agent image

The agent image is a standalone runtime. By default its entrypoint serves the
`webroot/index.html` placeholder on port 8080 — publish the port to reach it:

```bash
docker run --rm -p 8080:8080 tk-agent   # then open http://localhost:8080
```

To run a real app instead, re-enable the `python -m pipeline_lg` line in
`agent-entrypoint.sh` (it is present but commented out) and point it at your module.

Or via Compose (builds `tk-dev`, still needs `tk-agent` built first):

```bash
docker build -f docker/agent.Dockerfile -t tk-agent .
HOST_UID=$(id -u) HOST_GID=$(id -g) \
  docker compose -f docker/docker-compose.dev.yml run --build --rm dev
```
