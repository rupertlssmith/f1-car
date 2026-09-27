#!/bin/bash
set -euo pipefail

# =============================================================================
# Pinned, checksum-verified Kotlin DEV tools for the interactive dev image.
# Layered on top of the agent image's JVM (JDK 21 + Gradle); these are the
# hands-on tools you reach for at a prompt, not part of the production runtime.
#
#   * Kotlin compiler + REPL (kotlinc, kotlin) -> /opt/kotlin/kotlinc/bin
#   * ktlint (lint / format)                   -> /opt/kotlin/bin/ktlint
#
# Both are pure-JVM and arch-independent (they run on the base image's JDK).
# The dev Dockerfile puts both bin dirs on PATH. Requires: curl, unzip, sha256sum.
# =============================================================================

# --- Pins (bump version + matching checksum together) -----------------------
KOTLIN_VERSION="2.4.10"
KOTLIN_SHA="473dd66c7a3ef4b182065b3da670466c1bf2773a9dbb0ed8b33a39fe9d4f876d"

# ktlint ships only a GPG signature upstream, so this sha256 is pinned from the
# 1.8.0 self-executable artifact (recompute if you bump the version).
KTLINT_VERSION="1.8.0"
KTLINT_SHA="a3fd620207d5c40da6ca789b95e7f823c54e854b7fade7f613e91096a3706d75"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

verify() {  # verify <file> <expected-sha256>
    local actual
    actual="$(sha256sum "$1" | cut -d' ' -f1)"
    if [ "$actual" != "$2" ]; then
        echo "Checksum verification failed for $1" >&2
        echo "  expected $2" >&2
        echo "  actual   $actual" >&2
        exit 1
    fi
}

# --- Kotlin compiler + REPL --------------------------------------------------
kotlin_url="https://github.com/JetBrains/kotlin/releases/download/v${KOTLIN_VERSION}/kotlin-compiler-${KOTLIN_VERSION}.zip"

echo "Downloading Kotlin compiler ${KOTLIN_VERSION}..."
curl -fsSL -o "$TMP_DIR/kotlin.zip" "$kotlin_url"
verify "$TMP_DIR/kotlin.zip" "$KOTLIN_SHA"

echo "Installing Kotlin to /opt/kotlin/kotlinc..."
mkdir -p /opt/kotlin
unzip -q "$TMP_DIR/kotlin.zip" -d /opt/kotlin   # unpacks kotlinc/

# --- ktlint ------------------------------------------------------------------
ktlint_url="https://github.com/pinterest/ktlint/releases/download/${KTLINT_VERSION}/ktlint"

echo "Downloading ktlint ${KTLINT_VERSION}..."
curl -fsSL -o "$TMP_DIR/ktlint" "$ktlint_url"
verify "$TMP_DIR/ktlint" "$KTLINT_SHA"

echo "Installing ktlint to /opt/kotlin/bin/ktlint..."
mkdir -p /opt/kotlin/bin
install -m 0755 "$TMP_DIR/ktlint" /opt/kotlin/bin/ktlint

# --- Report ------------------------------------------------------------------
# kotlinc/ktlint shell out to java; ktlint's launcher needs it on PATH, so pin
# both here in case the build step runs before the image's env is in effect.
export JAVA_HOME="${JAVA_HOME:-/opt/java/current}"
export PATH="$JAVA_HOME/bin:$PATH"
echo ""
echo "✅ Kotlin dev tools installed:"
/opt/kotlin/kotlinc/bin/kotlinc -version 2>&1 | sed -n '1p'
/opt/kotlin/bin/ktlint --version
