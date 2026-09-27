# ============================================================
# devbox — the RUNTIME image: what runs the project in production.
#
# A complete, version-pinned environment for executing the project and nothing
# else: Python 3.14 in /opt/venv, the JVM build toolchain, the pandoc/xelatex
# render stack, and a headless Chromium. No editor, no Claude Code, no sudo —
# those belong to the dev image, which is built FROM this one
# (docker/dev.Dockerfile), so the stack a developer works against is by
# construction the stack production runs.
#
# Keep it that way: anything added here ships to production, so a tool that only
# helps while developing goes in the dev layer instead.
# ============================================================
FROM debian:bookworm
ARG DEBIAN_FRONTEND=noninteractive

LABEL org.opencontainers.image.description="devbox runtime — the production image for this project"

# 1) OS base + render stack + headless browser, in one apt layer.
#    TeX set is curated (NOT texlive-full): xetex engine + recommended + extra
#    (titlesec/enumitem/needspace live in -extra) + fonts-extra (TeX Gyre Pagella/
#    Heros). chromium gives Playwright a stable browser path — see CHROME_PATH
#    below. Drop the TeX and chromium lines if your project renders nothing and
#    drives no browser; they are the bulk of the image.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl gosu tini locales jq less unzip \
      python3 python3-venv python3-pip \
      pandoc \
      texlive-xetex texlive-latex-recommended texlive-latex-extra \
      texlive-fonts-recommended texlive-fonts-extra fonts-texgyre fontconfig \
      chromium \
 && rm -rf /var/lib/apt/lists/* \
 && sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen \
 && fc-cache -f

# 2) uv + Python 3.14 into an isolated venv at /opt/venv, deps installed with uv.
#    The project targets Python 3.14 (pyproject `requires-python`, `.python-version`);
#    Debian bookworm's apt python3 is 3.11, so we provision 3.14 via uv's managed
#    standalone build instead. Keeping the /opt/venv path means the dev image's
#    `/work/.venv -> /opt/venv` symlink and PATH keep resolving `python`/`pytest`/
#    `case-review` unchanged after the version bump. (Pin the uv tag as desired.)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY requirements.txt /tmp/requirements.txt
RUN uv python install 3.14 \
 && uv venv --python 3.14 /opt/venv \
 && VIRTUAL_ENV=/opt/venv uv pip install --no-cache -r /tmp/requirements.txt

# 3) A pinned, checksum-verified JVM build toolchain (Eclipse Temurin JDK 21 LTS
#    + Gradle) provisioned into /opt, mirroring how Python 3.14 is provisioned
#    outside apt. JAVA_HOME + PATH point at the stable /opt/java/current and
#    /opt/gradle/current symlinks (see ENV below), so a version bump inside the
#    script needs no edits here. Gradle drives Kotlin/JVM builds and pulls the
#    matching Kotlin compiler itself, so no Kotlin toolchain is baked into prod.
COPY docker/install_jvm.sh /tmp/install_jvm.sh
RUN /tmp/install_jvm.sh && rm /tmp/install_jvm.sh

# 4) A wrapper that runs chromium with the flags a container needs. Chromium's
#    sandbox can't initialise as a non-root user under Docker's default seccomp,
#    so pass --no-sandbox; --disable-dev-shm-usage avoids /dev/shm crashes.
#    Launch Playwright with executable_path=$CHROME_PATH (Python) or
#    executablePath (Node) and your own code needs no container-specific flags.
RUN printf '#!/bin/sh\nexec /usr/bin/chromium --no-sandbox --disable-dev-shm-usage "$@"\n' \
      > /usr/local/bin/pw-chromium \
 && chmod +x /usr/local/bin/pw-chromium

# 5) Your project source. Runtime state is excluded by .dockerignore and lives
#    on the mounted volume instead, so the image stays reproducible.
WORKDIR /app
COPY . /app

# 6) Entrypoint: resolve a non-root user, prepare the runtime root, drop privs.
COPY docker/_user-setup.sh /usr/local/lib/docker/_user-setup.sh
COPY docker/runtime-entrypoint.sh /usr/local/bin/runtime-entrypoint.sh
RUN chmod +x /usr/local/bin/runtime-entrypoint.sh

# APP_RUNTIME_DIR is where the project writes state that must outlive the
# container: it points at the mounted volume, and the entrypoint guarantees the
# directory exists and is writable before your code starts. Read it rather than
# hard-coding /runtime, so the same code works under `docker/run.sh`, under the
# dev container (where it points into the working tree) and on a laptop.
ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    JAVA_HOME=/opt/java/current \
    PATH=/opt/venv/bin:/opt/java/current/bin:/opt/gradle/current/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    PYTHONUNBUFFERED=1 \
    CHROME_PATH=/usr/local/bin/pw-chromium \
    APP_RUNTIME_DIR=/runtime

# Documentation only — `docker run -P` and readers of `docker image inspect`.
# docker/run.sh is what actually publishes ports (RUN_PORTS). 8080 is what the
# placeholder entrypoint serves; change it to whatever your app listens on, and
# make sure that listener binds 0.0.0.0 or no mapping can reach it.
EXPOSE 8080

# tini reaps zombies (chromium spawns children); the entrypoint execs your app.
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/runtime-entrypoint.sh"]
# No default args -> the entrypoint's default (the placeholder web server).
CMD []
