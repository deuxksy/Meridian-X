from meridian_x.classify import (
    _normalize_name,
    classify_filename,
    classify_folder,
    get_artist_folders,
    get_studio_mappings,
)


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
    assert classify_filename("ohmyholes.25.02.13.dakota.doll.mp4", config) == "Actors/Dakota Doll"
    assert classify_filename("dakota_doll_scene_01.mp4", config) == "Actors/Dakota Doll"
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
    assert classify_folder("dakota.doll.collection", config) == "Actors/Dakota Doll"
    assert classify_folder("vixen.studio.pack", config) == "Vixen"



from meridian_x.core import load_config

def test_dakota_doll_in_settings():
    config = load_config("config/settings.json")
    assert "Dakota Doll" in get_artist_folders(config)


def test_exxxtrasmall_studio_classification():
    config = load_config("config/settings.json")
    filename = "ExxxtraSmall.26.07.18.Random.Girl.XXX.1080p.MP4-WRB[XC].mp4"
    assert "ExxxtraSmall" in get_studio_mappings(config)
    assert classify_filename(filename, config) == "ExxxtraSmall"



def test_japanese_artists_classification():
    config = load_config("config/settings.json")
    artists = [
        "MINAMO", "Rena Miyashita", "Rima Arai", "Umi Yatsugake",
        "佐野葉月", "博多彩葉", "川越にこ", "日向由奈", "白花にあ", "雛形みくる"
    ]
    for artist in artists:
        assert artist in get_artist_folders(config)
    assert classify_filename("MINAMO_special_01.mp4", config) == "Actors/MINAMO"



from meridian_x.classify import classify_by_actress_lookup

def test_classify_by_actress_lookup():
    config = {
        "classify": {
            "artist_folders": ["MINAMO"]
        }
    }
    assert classify_by_actress_lookup("FNS-237.mp4", config, ["MINAMO"]) == "Actors/MINAMO"
    assert classify_by_actress_lookup("ABF-364.mp4", config, ["Unknown"]) is None


def test_structured_artists_and_studios_classification():
    config = {
        "classify": {
            "artists": {
                "WEST": ["Dakota Doll", "Molli Little"],
                "JPN": ["MINAMO"]
            },
            "studios": {
                "WEST": {
                    "Vixen": ["vixen", "tushy", "blacked"],
                    "TeamSkeet": ["teamskeet", "tiny4k"]
                }
            }
        }
    }
    # Artist priority
    assert classify_filename("ExxxtraSmall.Dakota.Doll.mp4", config) == "Actors/Dakota Doll"
    # Studio alias matching
    assert classify_filename("tushy.26.07.18.Remi.Raw.mp4", config) == "Vixen"
    assert classify_filename("tiny4k.26.07.18.mp4", config) == "TeamSkeet"

