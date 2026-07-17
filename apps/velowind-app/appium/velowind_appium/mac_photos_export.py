from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


DEFAULT_EXPORT_DIR = Path(__file__).resolve().parents[1] / "test-media" / "android"


def _export_dir() -> Path:
    raw_value = os.environ.get("VW_ANDROID_MEDIA_DIR")
    if raw_value:
        return Path(raw_value).expanduser()
    return DEFAULT_EXPORT_DIR


def _album_names_from_env() -> list[str] | None:
    raw_value = os.environ.get("VW_MAC_PHOTO_ALBUMS")
    if not raw_value:
        return None
    names = [name.strip() for name in raw_value.split(",")]
    return [name for name in names if name]


def _escape_applescript_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _build_applescript(export_dir: Path, album_names: list[str] | None) -> str:
    export_path = _escape_applescript_text(str(export_dir))
    if album_names:
        quoted_names = ", ".join(f'"{_escape_applescript_text(name)}"' for name in album_names)
        album_selection = f"set targetAlbumNames to {{{quoted_names}}}"
    else:
        album_selection = "set targetAlbumNames to name of albums"

    return f"""
set exportRoot to POSIX file "{export_path}"
tell application "Photos"
  {album_selection}
  repeat with albumName in targetAlbumNames
    try
      set albumRef to album (albumName as text)
      set mediaItems to media items of albumRef
      if (count of mediaItems) > 0 then
        set albumFolder to ((POSIX path of exportRoot) & "/" & (albumName as text))
        do shell script "mkdir -p " & quoted form of albumFolder
        export mediaItems to POSIX file albumFolder with using originals
      end if
    end try
  end repeat
end tell
"""


def export_mac_photos_albums(*, export_dir: Path, album_names: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    applescript = _build_applescript(export_dir, album_names)
    return subprocess.run(
        ["osascript", "-e", applescript],
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )


def main() -> int:
    export_dir = _export_dir()
    album_names = _album_names_from_env()
    shutil.rmtree(export_dir, ignore_errors=True)
    export_dir.mkdir(parents=True, exist_ok=True)

    if shutil.which("osascript") is None:
        print("Mac Photos export skipped: osascript is not available.")
        return 0

    print(f"Mac Photos export target dir: {export_dir}")
    if album_names:
        print(f"Mac Photos export albums: {', '.join(album_names)}")
    else:
        print("Mac Photos export albums: all albums")

    result = export_mac_photos_albums(export_dir=export_dir, album_names=album_names)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        print(result.stderr.strip() or "Mac Photos export failed.")
        return result.returncode or 1

    exported_files = [path for path in export_dir.rglob("*") if path.is_file()]
    print(f"Mac Photos export file count: {len(exported_files)}")
    print("Mac Photos export: completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
