#!/bin/sh

set -eu

MODE="${1:-}"
if [ -z "$MODE" ]; then
  echo "Usage: $0 <mode> [--udid <device-udid>]" >&2
  exit 1
fi
shift

while [ "$#" -gt 0 ]; do
  case "$1" in
    --avd)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --avd" >&2
        exit 1
      fi
      export VW_ANDROID_AVD="$2"
      shift 2
      ;;
    --target)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --target" >&2
        exit 1
      fi
      export VW_ANDROID_TARGET="$2"
      shift 2
      ;;
    --udid)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --udid" >&2
        exit 1
      fi
      export VW_ANDROID_UDID="$2"
      shift 2
      ;;
    --device-name)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --device-name" >&2
        exit 1
      fi
      export VW_ANDROID_DEVICE_NAME="$2"
      shift 2
      ;;
    --appium-server-url)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --appium-server-url" >&2
        exit 1
      fi
      export VW_APPIUM_SERVER_URL="$2"
      shift 2
      ;;
    *)
      echo "Unsupported argument: $1" >&2
      exit 1
      ;;
  esac
done

export VW_APPIUM_PLATFORM=android
export VW_ANDROID_TARGET="${VW_ANDROID_TARGET:-android_studio}"
export VW_ANDROID_APP_PACKAGE="${VW_ANDROID_APP_PACKAGE:-com.velowind.rider}"
export VW_ANDROID_APP_ACTIVITY="${VW_ANDROID_APP_ACTIVITY:-.MainActivity}"
export VW_LOGIN_USERNAME="${VW_LOGIN_USERNAME:-13381509990}"
export VW_LOGIN_PASSWORD="${VW_LOGIN_PASSWORD:-12345678}"
export VW_ANDROID_AVD="${VW_ANDROID_AVD:-}"
VW_ANDROID_APPIUM_LOG="${VW_ANDROID_APPIUM_LOG:-.tmp/appium-android/appium-server.log}"
VW_ANDROID_APPIUM_PID_FILE="${VW_ANDROID_APPIUM_PID_FILE:-.tmp/appium-android/appium-server.pid}"

case "$VW_ANDROID_TARGET" in
  android_studio)
    export VW_APPIUM_SERVER_URL="${VW_APPIUM_SERVER_URL:-http://127.0.0.1:4724}"
    export VW_ANDROID_DEVICE_NAME="${VW_ANDROID_DEVICE_NAME:-Android Emulator}"
    export VW_ANDROID_APP="${VW_ANDROID_APP:-/Users/test/Nancy/Testing/automation/android/寻风集_1.2.1.apk}"
    ;;
  mumu)
    export VW_APPIUM_SERVER_URL="${VW_APPIUM_SERVER_URL:-http://127.0.0.1:4725}"
    export VW_ANDROID_UDID="${VW_ANDROID_UDID:-127.0.0.1:16385}"
    export VW_ANDROID_DEVICE_NAME="${VW_ANDROID_DEVICE_NAME:-MuMu}"
    export VW_ANDROID_APP="${VW_ANDROID_APP:-/Users/test/Nancy/Testing/automation/android/寻风集_1.2.1.apk}"
    ;;
  *)
    echo "Unsupported Android target: $VW_ANDROID_TARGET" >&2
    exit 1
    ;;
esac

appium_bin_path() {
  if command -v pnpm >/dev/null 2>&1; then
    appium_bin=$(pnpm exec which appium 2>/dev/null || true)
    if [ -n "$appium_bin" ]; then
      printf '%s\n' "$appium_bin"
      return 0
    fi
  fi

  command -v appium
}

appium_server_host() {
  printf '%s\n' "$VW_APPIUM_SERVER_URL" | sed -E 's#^https?://([^/:]+).*$#\1#'
}

appium_server_port() {
  port=$(printf '%s\n' "$VW_APPIUM_SERVER_URL" | sed -nE 's#^https?://[^/:]+:([0-9]+).*$#\1#p')
  if [ -n "$port" ]; then
    printf '%s\n' "$port"
    return 0
  fi

  echo "VW_APPIUM_SERVER_URL must include an explicit port: $VW_APPIUM_SERVER_URL" >&2
  exit 1
}

local_appium_server_target() {
  case "$(appium_server_host)" in
    127.0.0.1|localhost)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

appium_server_is_reachable() {
  curl -fsS "${VW_APPIUM_SERVER_URL%/}/status" >/dev/null 2>&1
}

ensure_uiautomator2_driver_installed() {
  appium_bin=$(appium_bin_path || true)
  if [ -z "$appium_bin" ]; then
    echo "Appium CLI not found. Install it with \`npm install -g appium\`." >&2
    exit 1
  fi

  installed_drivers=$("$appium_bin" driver list --installed 2>&1 || true)
  if ! printf '%s\n' "$installed_drivers" | grep -iq 'uiautomator2'; then
    echo "Appium UiAutomator2 driver is not installed. Run \`appium driver install uiautomator2\`." >&2
    exit 1
  fi
}

wait_for_local_appium_server() {
  timeout_seconds="${1:-60}"
  started_at=$(date +%s)
  while :; do
    if appium_server_is_reachable; then
      return 0
    fi

    now=$(date +%s)
    if [ $((now - started_at)) -ge "$timeout_seconds" ]; then
      return 1
    fi
    sleep 1
  done
}

start_local_android_appium_server() {
  appium_bin=$(appium_bin_path)
  server_host=$(appium_server_host)
  server_port=$(appium_server_port)

  mkdir -p "$(dirname "$VW_ANDROID_APPIUM_LOG")"
  rm -f "$VW_ANDROID_APPIUM_PID_FILE"

  echo "Starting Android Appium server on ${server_host}:${server_port}"
  nohup "$appium_bin" server \
    --address "$server_host" \
    --port "$server_port" \
    --use-drivers=uiautomator2 \
    --log "$VW_ANDROID_APPIUM_LOG" \
    --log-timestamp >/tmp/velowind-android-appium.out 2>&1 &

  server_pid=$!
  printf '%s\n' "$server_pid" >"$VW_ANDROID_APPIUM_PID_FILE"

  if ! wait_for_local_appium_server 60; then
    echo "Android Appium server did not become ready in time. Check $VW_ANDROID_APPIUM_LOG and /tmp/velowind-android-appium.out" >&2
    exit 1
  fi
}

ensure_local_android_appium_server() {
  if [ "$VW_ANDROID_TARGET" != "android_studio" ]; then
    return 0
  fi

  if ! local_appium_server_target; then
    return 0
  fi

  ensure_uiautomator2_driver_installed

  if [ -f "$VW_ANDROID_APPIUM_PID_FILE" ]; then
    existing_pid=$(cat "$VW_ANDROID_APPIUM_PID_FILE" 2>/dev/null || true)
    if [ -n "$existing_pid" ] && kill -0 "$existing_pid" >/dev/null 2>&1 && appium_server_is_reachable; then
      return 0
    fi
    rm -f "$VW_ANDROID_APPIUM_PID_FILE"
  fi

  if appium_server_is_reachable; then
    echo "Appium server ${VW_APPIUM_SERVER_URL} is already running but is not managed by scripts/appium-android-local.sh. Stop that server or override VW_APPIUM_SERVER_URL." >&2
    exit 1
  fi

  start_local_android_appium_server
}

discover_online_emulator_udid() {
  adb devices | awk '$2 == "device" && $1 ~ /^emulator-/ { print $1; exit }'
}

pick_android_studio_avd() {
  if [ -n "$VW_ANDROID_AVD" ]; then
    printf '%s\n' "$VW_ANDROID_AVD"
    return 0
  fi

  if [ ! -x /Users/test/Library/Android/sdk/emulator/emulator ]; then
    return 1
  fi

  avds=$(/Users/test/Library/Android/sdk/emulator/emulator -list-avds 2>/dev/null || true)
  for preferred in velowind_api35 Pixel_10_Pro; do
    if printf '%s\n' "$avds" | grep -Fx "$preferred" >/dev/null 2>&1; then
      printf '%s\n' "$preferred"
      return 0
    fi
  done

  printf '%s\n' "$avds" | awk 'NF { print; exit }'
}

wait_for_android_studio_emulator() {
  timeout_seconds="${1:-180}"
  started_at=$(date +%s)
  while :; do
    udid=$(discover_online_emulator_udid)
    if [ -n "$udid" ]; then
      boot_completed=$(adb -s "$udid" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')
      if [ "$boot_completed" = "1" ]; then
        if [ -z "${VW_ANDROID_UDID:-}" ]; then
          export VW_ANDROID_UDID="$udid"
        fi
        return 0
      fi
    fi

    now=$(date +%s)
    if [ $((now - started_at)) -ge "$timeout_seconds" ]; then
      return 1
    fi
    sleep 2
  done
}

ensure_android_studio_emulator_online() {
  if [ "$VW_ANDROID_TARGET" != "android_studio" ]; then
    return 0
  fi

  if [ -n "${VW_ANDROID_UDID:-}" ]; then
    if adb devices | awk -v target="$VW_ANDROID_UDID" '$1 == target && $2 == "device" { found = 1 } END { exit found ? 0 : 1 }'; then
      return 0
    fi
  elif [ -n "$(discover_online_emulator_udid)" ]; then
    return 0
  fi

  avd_name=$(pick_android_studio_avd)
  if [ -z "$avd_name" ]; then
    echo "Unable to find an Android Studio AVD. Create one in Android Studio or pass --avd <name>." >&2
    exit 1
  fi

  echo "Starting Android Studio emulator AVD: $avd_name"
  nohup /Users/test/Library/Android/sdk/emulator/emulator -avd "$avd_name" >/tmp/velowind-android-emulator.out 2>&1 &

  if ! wait_for_android_studio_emulator 240; then
    echo "Android Studio emulator did not come online in time. Check /tmp/velowind-android-emulator.out" >&2
    exit 1
  fi
}

run_publish_suite() {
  PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m velowind_appium.run_android_tests \
    --suite apps/velowind-app/appium/test-suites/android-message-publish.yaml
}

run_activity_publish_suite() {
  PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m velowind_appium.run_android_tests \
    --suite apps/velowind-app/appium/test-suites/android-activity-publish.yaml
}

run_activity_session_suite() {
  PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m velowind_appium.run_android_tests \
    --suite apps/velowind-app/appium/test-suites/android-activity-session.yaml
}

run_default_suite() {
  PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m velowind_appium.run_android_tests
}

ensure_android_studio_emulator_online
ensure_local_android_appium_server
PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m velowind_appium.android_preflight

case "$MODE" in
  local)
    run_default_suite
    ;;
  publish)
    run_publish_suite
    ;;
  activity-publish)
    run_activity_publish_suite
    ;;
  activity-session)
    run_activity_session_suite
    ;;
  *)
    echo "Unsupported mode: $MODE" >&2
    exit 1
    ;;
esac
