#!/bin/bash
set -euo pipefail

# =============================================================================
# Pinned, checksum-verified JVM build toolchain for the AGENT (production) image.
#
#   * Eclipse Temurin JDK 21 (LTS)  -> /opt/java/temurin-<ver>,  /opt/java/current
#   * Gradle (build tool)           -> /opt/gradle/gradle-<ver>, /opt/gradle/current
#
# Arch-aware (x64/aarch64) in the same spirit as docker/install_claude.sh. The
# Dockerfile wires JAVA_HOME + PATH at the stable /opt/java/current and
# /opt/gradle/current symlinks, so bumping a version here needs no PATH change.
# Requires: curl, tar, unzip, sha256sum (installed in the apt layer).
# =============================================================================

# --- Pins (bump version + matching checksum together) -----------------------
JDK_VERSION="21.0.12+8"                 # Temurin 21 LTS point release
JDK_FILE_VERSION="21.0.12_8"            # filename form (+ -> _)
JDK_TAG="jdk-21.0.12%2B8"               # GitHub release tag, + URL-encoded as %2B
JDK_SHA_x64="e4446ff06a276155697597cc0f1b15da004ff083f4964a35271ecee567177370"
JDK_SHA_aarch64="eba38e871b02d407897bfe017ea35352dfc1420ef6d2112425b0c67325ca509d"

GRADLE_VERSION="9.6.1"
GRADLE_SHA="9c0f7faeeb306cb14e4279a3e084ca6b596894089a0638e68a07c945a32c9e14"

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

# --- Architecture ------------------------------------------------------------
case "$(uname -m)" in
    x86_64|amd64)  jdk_arch="x64";     jdk_sha="$JDK_SHA_x64" ;;
    arm64|aarch64) jdk_arch="aarch64"; jdk_sha="$JDK_SHA_aarch64" ;;
    *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

# --- Temurin JDK -------------------------------------------------------------
jdk_file="OpenJDK21U-jdk_${jdk_arch}_linux_hotspot_${JDK_FILE_VERSION}.tar.gz"
jdk_url="https://github.com/adoptium/temurin21-binaries/releases/download/${JDK_TAG}/${jdk_file}"

echo "Downloading Temurin JDK ${JDK_VERSION} (${jdk_arch})..."
curl -fsSL -o "$TMP_DIR/jdk.tar.gz" "$jdk_url"
verify "$TMP_DIR/jdk.tar.gz" "$jdk_sha"

echo "Installing JDK to /opt/java/temurin-${JDK_VERSION}..."
mkdir -p "/opt/java/temurin-${JDK_VERSION}"
tar -xzf "$TMP_DIR/jdk.tar.gz" -C "/opt/java/temurin-${JDK_VERSION}" --strip-components=1
ln -sfn "/opt/java/temurin-${JDK_VERSION}" /opt/java/current

# --- Gradle ------------------------------------------------------------------
gradle_url="https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip"

echo "Downloading Gradle ${GRADLE_VERSION}..."
curl -fsSL -o "$TMP_DIR/gradle.zip" "$gradle_url"
verify "$TMP_DIR/gradle.zip" "$GRADLE_SHA"

echo "Installing Gradle to /opt/gradle/gradle-${GRADLE_VERSION}..."
mkdir -p /opt/gradle
unzip -q "$TMP_DIR/gradle.zip" -d /opt/gradle   # unpacks gradle-${GRADLE_VERSION}/
ln -sfn "/opt/gradle/gradle-${GRADLE_VERSION}" /opt/gradle/current

# --- Report ------------------------------------------------------------------
# The Dockerfile's JAVA_HOME/PATH env is applied after this step runs, so set
# JAVA_HOME here for the gradle launcher (it shells out to $JAVA_HOME/bin/java).
export JAVA_HOME=/opt/java/current
echo ""
echo "✅ JVM toolchain installed:"
"$JAVA_HOME/bin/java" -version
/opt/gradle/current/bin/gradle --version | sed -n '/^Gradle /p'
