from velowind_appium import mac_photos_export


def test_album_names_from_env_returns_none_when_missing(monkeypatch):
    monkeypatch.delenv("VW_MAC_PHOTO_ALBUMS", raising=False)

    assert mac_photos_export._album_names_from_env() is None


def test_album_names_from_env_splits_and_trims(monkeypatch):
    monkeypatch.setenv("VW_MAC_PHOTO_ALBUMS", "云南洱海, 长白山 , ,北京")

    assert mac_photos_export._album_names_from_env() == ["云南洱海", "长白山", "北京"]


def test_build_applescript_includes_requested_album_names(tmp_path):
    script = mac_photos_export._build_applescript(tmp_path, ["云南洱海", "长白山"])

    assert 'set targetAlbumNames to {"云南洱海", "长白山"}' in script
    assert str(tmp_path) in script
