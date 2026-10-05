#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
if [ -z "${JAVA_HOME:-}" ] && [ -d "$PWD/.tools/jdk/Contents/Home" ]; then
    export JAVA_HOME="$PWD/.tools/jdk/Contents/Home"
fi
if [ -z "${ANDROID_HOME:-}" ] && [ -d "$PWD/.tools/android-sdk" ]; then
    export ANDROID_HOME="$PWD/.tools/android-sdk"
fi
export GRADLE_USER_HOME="${GRADLE_USER_HOME:-$PWD/.tools/gradle-cache}"
./gradlew --no-daemon :stream-core:test :glasses-app:assembleDebug :android-app:assembleDebug :glasses-app:lintDebug :android-app:lintDebug
mkdir -p .tools/test-classes
"${JAVA_HOME}/bin/javac" -cp stream-core/build/classes/java/main -d .tools/test-classes tools/java/RelayHarness.java
python3 -m unittest discover -s tests -v
