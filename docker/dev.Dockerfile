# ============================================================
# tk — interactive DEV environment.
#
# The agent toolchain PLUS Claude Code, for hands-on development. Built FROM the
# agent image so the heavy render/Python stack (pandoc/xelatex, /opt/venv,
# pw-chromium, CHROME_PATH) is defined in exactly one place; this layer only adds
# Claude Code + dev conveniences. Not a deployment image — see docker/agent.Dockerfile
# for that.
#
# Build (agent image first, it is the base):
#   docker build -f docker/agent.Dockerfile -t tk-agent .
#   docker build -f docker/dev.Dockerfile   -t tk-dev   .
# Enter:  ./docker/dev.sh   (interactive bash; then run `claude` or `python -m pipeline_lg`)
# ============================================================
FROM tk-agent:latest
ARG DEBIAN_FRONTEND=noninteractive

LABEL org.opencontainers.image.description="tk interactive dev environment (agent + Claude Code)"

# 1) Dev conveniences + git/sudo, in one apt layer.
RUN apt-get update && apt-get install -y --no-install-recommends \
      git sudo ripgrep fd-find vim-tiny bash-completion man-db \
 && rm -rf /var/lib/apt/lists/*

# 2) Claude Code (standalone binary -> /opt/claude, symlink /usr/local/bin/claude;
#    checksum-verified, no npm dependency). Auth/history persist in the home volume.
COPY docker/install_claude.sh /tmp/install_claude.sh
RUN /tmp/install_claude.sh && rm /tmp/install_claude.sh

# 3) Kotlin dev tools (kotlinc + REPL, ktlint), pinned + checksum-verified into
#    /opt/kotlin. These ride on the agent image's JDK 21; production builds with
#    Gradle (which fetches its own Kotlin), so the standalone compiler/REPL and
#    linter are a dev-only convenience and live only in this layer.
COPY docker/install_kotlin.sh /tmp/install_kotlin.sh
RUN /tmp/install_kotlin.sh && rm /tmp/install_kotlin.sh

# Non-login shells: put the Kotlin bins ahead of the inherited PATH (which
# already carries JDK + Gradle from the agent image). JAVA_HOME is inherited too.
ENV PATH=/opt/kotlin/kotlinc/bin:/opt/kotlin/bin:$PATH

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
      > /etc/profile.d/10-pipeline-path.sh

# 5) Dev works on the bind-mounted repo at /work, not the agent image's baked
#    /app. Blank PIPELINE_RUNTIME_BASE so pipeline_lg falls back to its default
#    (<repo>/runtime = /work/runtime) — runs stay visible on the host.
WORKDIR /work
ENV PIPELINE_RUNTIME_BASE=

# 6) Entrypoint: resolve a host-matching user (shared helper), grant sudo, set
#    HOME/PATH, symlink /work/.venv -> /opt/venv, drop privileges.
COPY docker/_user-setup.sh /usr/local/lib/docker/_user-setup.sh
COPY docker/dev-entrypoint.sh /usr/local/bin/dev-entrypoint.sh
RUN chmod +x /usr/local/bin/dev-entrypoint.sh

# tini reaps zombies (chromium spawns children); entrypoint execs the shell.
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/dev-entrypoint.sh"]
CMD ["bash"]
