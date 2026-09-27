# ============================================================
# f1-car — interactive DEV environment.
#
# The runtime toolchain PLUS Claude Code, for hands-on development. Built FROM the
# runtime image so the heavy render/Python stack (pandoc/xelatex, /opt/venv,
# pw-chromium, CHROME_PATH) is defined in exactly one place; this layer only adds
# Claude Code + dev conveniences. Not a deployment image — see docker/runtime.Dockerfile
# for that.
#
# Build (runtime image first, it is the base):
#   docker build -f docker/runtime.Dockerfile -t f1-car-runtime .
#   docker build -f docker/dev.Dockerfile   -t f1-car-dev   .
# Enter:  ./docker/dev.sh   (interactive bash; then run `claude`, `python`, `gradle`, …)
#
# Ports: dev.sh publishes DEV_PORTS (8000 and 8080 by default) — see the EXPOSE
# note near the bottom of this file.
# ============================================================
FROM f1-car-runtime:latest
ARG DEBIAN_FRONTEND=noninteractive

LABEL org.opencontainers.image.description="f1-car interactive dev environment (runtime + Claude Code)"

# 1) Dev conveniences + git/sudo, in one apt layer.
RUN apt-get update && apt-get install -y --no-install-recommends \
      git sudo ripgrep fd-find vim-tiny bash-completion man-db \
 && rm -rf /var/lib/apt/lists/*

# 2) Claude Code (standalone binary -> /opt/claude, symlink /usr/local/bin/claude;
#    checksum-verified, no npm dependency). Auth/history persist in the home volume.
COPY docker/install_claude.sh /tmp/install_claude.sh
RUN /tmp/install_claude.sh && rm /tmp/install_claude.sh

# 3) Kotlin dev tools (kotlinc + REPL, ktlint), pinned + checksum-verified into
#    /opt/kotlin. These ride on the runtime image's JDK 21; production builds with
#    Gradle (which fetches its own Kotlin), so the standalone compiler/REPL and
#    linter are a dev-only convenience and live only in this layer.
COPY docker/install_kotlin.sh /tmp/install_kotlin.sh
RUN /tmp/install_kotlin.sh && rm /tmp/install_kotlin.sh

# Non-login shells: put the Kotlin bins ahead of the inherited PATH (which
# already carries JDK + Gradle from the runtime image). JAVA_HOME is inherited too.
ENV PATH=/opt/kotlin/kotlinc/bin:/opt/kotlin/bin:$PATH

# 3b) BeamNG mod tooling: headless Blender for preview renders
#     (tools/rb14/render.py; its glTF importer needs python3-numpy), assimp
#     CLI for mesh inspection/conversion, ImageMagick for textures, and git-lfs
#     for the model/texture files. Collada (.dae) is read and written by
#     tools/rb14/dae.py, so Blender's own Collada support is not needed (the
#     Debian/Ubuntu builds leave it out). trimesh (mesh checks) and xxhash (mod
#     manifest hashes, tools/build_mod.py) go into the project venv. Dev-only,
#     so none of this reaches the runtime image.
RUN apt-get update && apt-get install -y --no-install-recommends \
      blender python3-numpy assimp-utils imagemagick git-lfs \
 && rm -rf /var/lib/apt/lists/* \
 && VIRTUAL_ENV=/opt/venv uv pip install --no-cache trimesh numpy xxhash

# 4) Colour aliases + bash completion (eco-dev style; TERM is set by dev.sh).
RUN printf '%s\n' \
      'alias ls="ls --color=auto"' \
      'alias ll="ls -la --color=auto"' \
      'alias grep="grep --color=auto"' \
      'alias fd="fdfind"' \
      'alias rg="rg --smart-case"' \
      '[ -f /etc/bash_completion ] && . /etc/bash_completion' \
      >> /etc/bash.bashrc \
 # Debian's /etc/profile hard-resets PATH, so a *login* shell (bash -l) would drop
 # /opt/venv/bin and the JVM/Kotlin bins. Re-assert the venv + per-user bin + the
 # JDK/Gradle/Kotlin toolchain (and JAVA_HOME) for login shells too, so
 # `python`/`java`/`gradle`/`kotlinc` resolve regardless of how the shell started.
 && printf '%s\n' \
      'export JAVA_HOME=/opt/java/current' \
      'export PATH="$HOME/.local/bin:/opt/venv/bin:/opt/java/current/bin:/opt/gradle/current/bin:/opt/kotlin/kotlinc/bin:/opt/kotlin/bin:$PATH"' \
      > /etc/profile.d/10-f1-car-path.sh

# 5) Dev works on the bind-mounted repo at /work, not the runtime image's baked
#    /app.
WORKDIR /work

#    THE ENV AUDIT. Every variable the base image sets for its own deployment is
#    inherited here, and the dangerous ones are those that make the container run
#    BAKED artifacts against EDITED sources: the change is silently ignored and
#    there is no error to explain it. Whenever you add such a flag to the runtime
#    image — a skip-the-build switch, a "use the compiled bundle" toggle, a
#    baked config path — clear it in this block as well.
#
#    APP_RUNTIME_DIR is the worked example: the runtime image points it at the
#    /runtime volume, which a dev container does not mount. Repointing it into
#    the bind-mounted tree keeps state on the host, where you can read it with
#    an editor and delete it with rm.
ENV APP_RUNTIME_DIR=/work/runtime

# Documentation only — `docker run -P` and readers of `docker image inspect`.
# dev.sh is what actually publishes ports, and it publishes DEV_PORTS regardless
# of what is listed here. Each server must bind 0.0.0.0 inside the container to
# be reachable; most dev servers default to loopback and need telling.
EXPOSE 8000 8080

# 6) Entrypoint: resolve a host-matching user (shared helper), put that user's
#    HOME on the volume dev.sh mounts (DEV_HOME), grant sudo, set HOME/PATH,
#    symlink /work/.venv -> /opt/venv, drop privileges.
COPY docker/_user-setup.sh /usr/local/lib/docker/_user-setup.sh
COPY docker/dev-entrypoint.sh /usr/local/bin/dev-entrypoint.sh
RUN chmod +x /usr/local/bin/dev-entrypoint.sh

# tini reaps zombies (chromium spawns children); entrypoint execs the shell.
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/dev-entrypoint.sh"]
CMD ["bash"]
