#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
if [ -z "${JAVA_HOME:-}" ] && [ -d "$PWD/.tools/jdk/Contents/Home" ]; then export JAVA_HOME="$PWD/.tools/jdk/Contents/Home"; fi
if [ -z "${ANDROID_HOME:-}" ] && [ -d "$PWD/.tools/android-sdk" ]; then export ANDROID_HOME="$PWD/.tools/android-sdk"; fi
export GRADLE_USER_HOME="${GRADLE_USER_HOME:-$PWD/.tools/gradle-cache}"
./gradlew --no-daemon :glasses-app:assembleDebug :android-app:assembleDebug
mkdir -p output/apk
cp glasses-app/build/outputs/apk/debug/glasses-app-debug.apk output/apk/cs536-glasses-debug.apk
cp android-app/build/outputs/apk/debug/android-app-debug.apk output/apk/cs536-phone-debug.apk
