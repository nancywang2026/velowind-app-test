from __future__ import annotations

import os
import hashlib
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .android_config import load_android_config


DEFAULT_MEDIA_DIR = Path(__file__).resolve().parents[1] / "test-media" / "android"
DEVICE_CAMERA_DIR = "/sdcard/DCIM/Camera"
DEVICE_PICTURES_DIR = "/sdcard/Pictures"
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
GALLERY_PACKAGE = "com.android.gallery3d"
GALLERY_ACTIVITY = "com.android.gallery3d/.app.GalleryActivity"


def _media_dir() -> Path:
    raw_value = os.environ.get("VW_ANDROID_MEDIA_DIR")
    if raw_value:
        return Path(raw_value).expanduser()
    return DEFAULT_MEDIA_DIR


@dataclass(frozen=True)
class MediaAsset:
    source_path: Path
    relative_dir: Path


def discover_media_assets(media_dir: Path) -> list[MediaAsset]:
    if not media_dir.exists() or not media_dir.is_dir():
        return []

    assets = [
        MediaAsset(
            source_path=path,
            relative_dir=path.relative_to(media_dir).parent,
        )
        for path in media_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    return sorted(assets, key=lambda asset: (str(asset.relative_dir), asset.source_path.name))


def discover_media_files(media_dir: Path) -> list[Path]:
    return [asset.source_path for asset in discover_media_assets(media_dir)]


def build_device_target_dir(asset: MediaAsset) -> str:
    if asset.relative_dir == Path("."):
        return DEVICE_CAMERA_DIR
    relative = "/".join(asset.relative_dir.parts)
    return f"{DEVICE_PICTURES_DIR}/{relative}"


def _adb(*args: str, udid: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["adb", "-s", udid, *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )


def prepare_video_fixture(*, udid: str, source_path: Path) -> tuple[int, ...]:
    """Stage a fixture and return its device-local picker timestamp."""
    source_path = Path(source_path).expanduser().resolve()
    if not udid or not source_path.is_file():
        raise AssertionError(f"Android video fixture requires a device and source file: {source_path}")
    digest = hashlib.sha256()
    with source_path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    album = f"VWVideo_{digest.hexdigest()[:12]}"
    target_dir = f"/sdcard/Pictures/{album}"
    target_path = f"{target_dir}/source{source_path.suffix.lower()}"
    commands = [
        ("shell", "mkdir", "-p", target_dir),
        ("push", str(source_path), target_path),
        ("shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", f"file://{target_path}"),
    ]
    for command in commands:
        result = _adb(*command, udid=udid)
        if result.returncode != 0:
            raise AssertionError(f"Unable to prepare Android video fixture: {result.stderr or result.stdout}")
    # Broadcast delivery can precede MediaStore indexing. Do not open a picker
    # until the file is indexed, and never fall back to the user's recent media.
    end_at = time.monotonic() + 30
    indexed_suffix = f"/Pictures/{album}/{Path(target_path).name}"
    while time.monotonic() < end_at:
        result = _adb(
            "shell", "content", "query", "--uri", "content://media/external/video/media",
            "--projection", "datetaken:_data", udid=udid,
        )
        matching = [line for line in result.stdout.splitlines() if line.strip().endswith(indexed_suffix)]
        if result.returncode == 0 and len(matching) == 1:
            match = re.search(r"datetaken=(\d+),", matching[0])
            if match and int(match.group(1)) > 0:
                # Use the same device-local capture date shown in the picker's
                # accessibility description. Do not infer identity from sort
                # order or change metadata managed by Android's media scanner.
                epoch = int(match.group(1)) // 1000
                date = _adb("shell", "date", "-d", f"@{epoch}", "+%Y,%m,%d,%H,%M,%S", udid=udid)
                fields = date.stdout.strip().split(",")
                if date.returncode != 0 or len(fields) != 6 or not all(value.isdigit() for value in fields):
                    raise AssertionError("Unable to read device-local capture time for Android video selection")
                return tuple(map(int, fields))
        time.sleep(0.5)
    raise AssertionError(f"Android video fixture was not indexed: {target_path}")


def sync_media_to_android_device(*, udid: str, media_assets: list[MediaAsset]) -> tuple[int, list[str]]:
    messages: list[str] = []
    prepared_dirs: set[str] = set()
    physical_device = is_physical_android_device_udid(udid)

    if physical_device:
        messages.append(f"Android media cleanup skipped for physical device: {udid}")
    else:
        cleanup_exit_code, cleanup_messages = clear_synced_media_from_android_device(udid=udid)
        messages.extend(cleanup_messages)
        if cleanup_exit_code != 0:
            return cleanup_exit_code, messages

    for asset in media_assets:
        for target_dir in _target_dirs_for_asset(asset):
            if target_dir not in prepared_dirs:
                mkdir_result = _adb("shell", f"mkdir -p '{target_dir}'", udid=udid)
                if mkdir_result.returncode != 0:
                    messages.append(mkdir_result.stderr.strip() or f"Unable to create Android media directory: {target_dir}")
                    return mkdir_result.returncode or 1, messages
                prepared_dirs.add(target_dir)

            target_path = f"{target_dir}/{asset.source_path.name}"
            if is_physical_android_device_udid(udid) and android_media_file_exists(udid=udid, target_path=target_path):
                messages.append(f"Android media already present: {target_path}")
                continue

            push_result = _adb("push", str(asset.source_path), f"{target_dir}/", udid=udid)
            if push_result.returncode != 0:
                messages.append(push_result.stderr.strip() or f"Unable to push {asset.source_path.name}")
                return push_result.returncode or 1, messages
            messages.append(push_result.stdout.strip() or f"Pushed {asset.source_path.name} -> {target_dir}")

            scan_result = _adb(
                "shell",
                "am",
                "broadcast",
                "-a",
                "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                "-d",
                f"file://{target_path}",
                udid=udid,
            )
            if scan_result.returncode != 0:
                messages.append(scan_result.stderr.strip() or f"Unable to scan {asset.source_path.name}")
                return scan_result.returncode or 1, messages

    refresh_exit_code, refresh_messages = refresh_android_gallery_cache(udid=udid)
    messages.extend(refresh_messages)
    if refresh_exit_code != 0:
        return refresh_exit_code, messages

    return 0, messages


def refresh_android_gallery_cache(*, udid: str) -> tuple[int, list[str]]:
    messages: list[str] = []

    force_stop_before = _adb("shell", "am", "force-stop", GALLERY_PACKAGE, udid=udid)
    if force_stop_before.returncode != 0:
        if not _gallery_refresh_unavailable(force_stop_before):
            messages.append(force_stop_before.stderr.strip() or "Unable to stop Android gallery before refresh")
            return force_stop_before.returncode or 1, messages

    start_result = _adb("shell", "am", "start", "-n", GALLERY_ACTIVITY, udid=udid)
    if start_result.returncode != 0:
        if _gallery_refresh_unavailable(start_result):
            messages.append("Android gallery refresh skipped: Gallery3D is unavailable on this device")
            return 0, messages
        messages.append(start_result.stderr.strip() or "Unable to launch Android gallery for refresh")
        return start_result.returncode or 1, messages
    messages.append(start_result.stdout.strip() or "Android gallery refresh launch requested")

    time.sleep(2)

    force_stop_after = _adb("shell", "am", "force-stop", GALLERY_PACKAGE, udid=udid)
    if force_stop_after.returncode != 0:
        messages.append(force_stop_after.stderr.strip() or "Unable to stop Android gallery after refresh")
        return force_stop_after.returncode or 1, messages

    messages.append("Android gallery cache refreshed")
    return 0, messages


def _gallery_refresh_unavailable(result: subprocess.CompletedProcess[str]) -> bool:
    combined = f"{result.stdout}\n{result.stderr}".strip()
    return any(
        marker in combined
        for marker in [
            "does not exist",
            "No activity found",
            "Unknown package",
            "not found",
        ]
    )


def clear_synced_media_from_android_device(*, udid: str) -> tuple[int, list[str]]:
    messages: list[str] = []
    cleanup_commands = [
        f"rm -f {DEVICE_CAMERA_DIR}/*",
        f"find {DEVICE_PICTURES_DIR} -mindepth 1 -maxdepth 1 ! -name '.thumbnails' -exec rm -rf {{}} +",
    ]
    for command in cleanup_commands:
        result = _adb("shell", command, udid=udid)
        if result.returncode != 0:
            messages.append(result.stderr.strip() or f"Unable to clean Android media via: {command}")
            return result.returncode or 1, messages
    messages.append("Android media cleanup: completed")
    return 0, messages


def is_physical_android_device_udid(udid: str) -> bool:
    return bool(udid.strip()) and not udid.startswith("emulator-") and ":" not in udid


def android_media_file_exists(*, udid: str, target_path: str) -> bool:
    result = _adb("shell", f"test -e '{target_path}'", udid=udid)
    return result.returncode == 0


def _target_dirs_for_asset(asset: MediaAsset) -> list[str]:
    target_dirs = [build_device_target_dir(asset)]
    if asset.relative_dir != Path("."):
        target_dirs.append(DEVICE_CAMERA_DIR)
    return target_dirs


def main() -> int:
    config = load_android_config()
    if not config.udid:
        print("Android media sync skipped: no online device found.")
        return 0

    media_dir = _media_dir()
    media_assets = discover_media_assets(media_dir)
    if not media_assets:
        print(f"Android media sync skipped: no supported media found in {media_dir}")
        return 0

    print(f"Android media sync target: {config.udid}")
    print(f"Android media source dir: {media_dir}")
    print(f"Android media file count: {len(media_assets)}")

    exit_code, messages = sync_media_to_android_device(udid=config.udid, media_assets=media_assets)
    for message in messages:
        print(message)

    if exit_code == 0:
        print("Android media sync: completed")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
