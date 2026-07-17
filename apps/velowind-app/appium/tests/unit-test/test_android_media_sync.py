from pathlib import Path

from velowind_appium import android_media_sync


def test_discover_media_assets_preserves_album_subdirectories(tmp_path):
    album_dir = tmp_path / "云南洱海"
    album_dir.mkdir()
    (album_dir / "a.jpg").write_text("jpg", encoding="utf-8")
    (tmp_path / "root.png").write_text("png", encoding="utf-8")

    assets = android_media_sync.discover_media_assets(tmp_path)

    assert assets == [
        android_media_sync.MediaAsset(source_path=tmp_path / "root.png", relative_dir=Path(".")),
        android_media_sync.MediaAsset(source_path=album_dir / "a.jpg", relative_dir=Path("云南洱海")),
    ]


def test_discover_media_files_filters_supported_extensions(tmp_path):
    (tmp_path / "a.jpg").write_text("jpg", encoding="utf-8")
    (tmp_path / "b.png").write_text("png", encoding="utf-8")
    (tmp_path / "c.txt").write_text("txt", encoding="utf-8")
    (tmp_path / "nested").mkdir()

    discovered = android_media_sync.discover_media_files(tmp_path)

    assert discovered == [tmp_path / "a.jpg", tmp_path / "b.png"]


def test_discover_media_files_returns_empty_when_missing(tmp_path):
    discovered = android_media_sync.discover_media_files(tmp_path / "missing")

    assert discovered == []


def test_build_device_target_dir_uses_camera_for_root_files(tmp_path):
    asset = android_media_sync.MediaAsset(source_path=tmp_path / "a.jpg", relative_dir=Path("."))

    assert android_media_sync.build_device_target_dir(asset) == android_media_sync.DEVICE_CAMERA_DIR


def test_build_device_target_dir_uses_pictures_subdirectory_for_album_files(tmp_path):
    asset = android_media_sync.MediaAsset(source_path=tmp_path / "a.jpg", relative_dir=Path("云南洱海"))

    assert android_media_sync.build_device_target_dir(asset) == "/sdcard/Pictures/云南洱海"


def test_target_dirs_for_album_asset_include_album_and_camera(tmp_path):
    asset = android_media_sync.MediaAsset(source_path=tmp_path / "a.jpg", relative_dir=Path("云南洱海"))

    assert android_media_sync._target_dirs_for_asset(asset) == [
        "/sdcard/Pictures/云南洱海",
        android_media_sync.DEVICE_CAMERA_DIR,
    ]


def test_target_dirs_for_root_asset_only_include_camera(tmp_path):
    asset = android_media_sync.MediaAsset(source_path=tmp_path / "a.jpg", relative_dir=Path("."))

    assert android_media_sync._target_dirs_for_asset(asset) == [android_media_sync.DEVICE_CAMERA_DIR]


def test_clear_synced_media_from_android_device_removes_camera_and_album_dirs(monkeypatch):
    calls = []

    class Result:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    monkeypatch.setattr(
        android_media_sync,
        "_adb",
        lambda *args, udid: calls.append((args, udid)) or Result(),
    )

    exit_code, messages = android_media_sync.clear_synced_media_from_android_device(udid="127.0.0.1:16385")

    assert exit_code == 0
    assert calls == [
        (("shell", f"rm -f {android_media_sync.DEVICE_CAMERA_DIR}/*"), "127.0.0.1:16385"),
        (("shell", f"find {android_media_sync.DEVICE_PICTURES_DIR} -mindepth 1 -maxdepth 1 ! -name '.thumbnails' -exec rm -rf {{}} +"), "127.0.0.1:16385"),
    ]
    assert messages == ["Android media cleanup: completed"]


def test_refresh_android_gallery_cache_restarts_gallery(monkeypatch):
    calls = []

    class Result:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    monkeypatch.setattr(
        android_media_sync,
        "_adb",
        lambda *args, udid: calls.append((args, udid)) or Result(stdout="ok"),
    )
    monkeypatch.setattr(android_media_sync.time, "sleep", lambda seconds: None)

    exit_code, messages = android_media_sync.refresh_android_gallery_cache(udid="127.0.0.1:16385")

    assert exit_code == 0
    assert calls == [
        (("shell", "am", "force-stop", "com.android.gallery3d"), "127.0.0.1:16385"),
        (("shell", "am", "start", "-n", "com.android.gallery3d/.app.GalleryActivity"), "127.0.0.1:16385"),
        (("shell", "am", "force-stop", "com.android.gallery3d"), "127.0.0.1:16385"),
    ]
    assert messages[-1] == "Android gallery cache refreshed"


def test_refresh_android_gallery_cache_skips_when_gallery3d_activity_is_unavailable(monkeypatch):
    calls = []

    class Result:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    results = iter([
        Result(stdout=""),
        Result(returncode=1, stderr="Error type 3\nError: Activity class {com.android.gallery3d/com.android.gallery3d.app.GalleryActivity} does not exist."),
    ])

    monkeypatch.setattr(
        android_media_sync,
        "_adb",
        lambda *args, udid: calls.append((args, udid)) or next(results),
    )

    exit_code, messages = android_media_sync.refresh_android_gallery_cache(udid="127.0.0.1:16385")

    assert exit_code == 0
    assert calls == [
        (("shell", "am", "force-stop", "com.android.gallery3d"), "127.0.0.1:16385"),
        (("shell", "am", "start", "-n", "com.android.gallery3d/.app.GalleryActivity"), "127.0.0.1:16385"),
    ]
    assert messages == ["Android gallery refresh skipped: Gallery3D is unavailable on this device"]
