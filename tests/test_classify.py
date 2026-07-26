import pytest
from meridian_x.classify import _normalize_name, classify_filename, classify_folder


def test_normalize_name():
    assert _normalize_name("Dakota.Doll") == "dakotadoll"
    assert _normalize_name("dakota_doll") == "dakotadoll"
    assert _normalize_name("Dakota Doll") == "dakotadoll"
    assert _normalize_name("ohmyholes.25.02.13.dakota.doll.mp4") == "ohmyholes250213dakotadollmp4"

def test_classify_filename_with_normalized_artist():
    config = {
        "classify": {
            "artist_folders": ["Dakota Doll"],
            "studio_folders": ["Vixen"]
        }
    }
    assert classify_filename("ohmyholes.25.02.13.dakota.doll.mp4", config) == "Dakota Doll"
    assert classify_filename("dakota_doll_scene_01.mp4", config) == "Dakota Doll"
    assert classify_filename("Vixen.24.01.01.random.scene.mp4", config) == "Vixen"
    assert classify_filename("GVH-864.mp4", config) == "JPN"
    assert classify_filename("FC2-PPV-4930952.mp4", config) == "FC2"
    assert classify_filename("random_western_file.mp4", config) == "West"

def test_classify_folder_with_normalized_artist():
    config = {
        "classify": {
            "artist_folders": ["Dakota Doll"],
            "studio_folders": ["Vixen"]
        }
    }
    assert classify_folder("dakota.doll.collection", config) == "Dakota Doll"
    assert classify_folder("vixen.studio.pack", config) == "Vixen"


from meridian_x.core import load_config

def test_dakota_doll_in_settings():
    config = load_config("config/settings.json")
    assert "Dakota Doll" in config.get("classify", {}).get("artist_folders", [])


def test_exxxtrasmall_studio_classification():
    config = load_config("config/settings.json")
    filename = "ExxxtraSmall.26.07.18.Remi.Raw.And.Alli.Skye.XXX.1080p.MP4-WRB[XC].mp4"
    assert "ExxxtraSmall" in config.get("classify", {}).get("studio_folders", [])
    assert classify_filename(filename, config) == "ExxxtraSmall"


