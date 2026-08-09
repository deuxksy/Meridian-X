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


class TestComputeExcludeFolders:
    """compute_exclude_folders: 폴더 분류 제외 집합 (분류 목적지 보호)."""

    def test_includes_actors_container(self):
        """회귀: Actors/ 컨테이너 자체가 분류 대상 폴더로 재분류되면 안 된다."""
        from meridian_x.classify import compute_exclude_folders
        config = {"classify": {}, "genres": {}}
        assert "Actors" in compute_exclude_folders(config)

    def test_full_set_from_dict_config(self):
        from meridian_x.classify import compute_exclude_folders
        config = {
            "classify": {
                "artists": {"WEST": ["Dakota Doll"], "JPN": ["MINAMO"]},
                "studios": {"WEST": {"Vixen": ["vixen", "tushy"]}, "JPN": {}},
            },
            "genres": {"Anime": {"keywords": [], "prefixes": []}},
        }
        exclude = set(compute_exclude_folders(config))
        assert {
            "Actors", "JPN", "FC2", "West",
            "Dakota Doll", "MINAMO", "Vixen", "Anime",
        } <= exclude


from unittest.mock import patch
from meridian_x.classify import classify_filename_with_metadata


@patch("meridian_x.classify.get_jav_metadata")
def test_classify_filename_with_metadata_actress(mock_get_meta):
    mock_get_meta.return_value = {
        "code": "SONE-446",
        "actresses": ["MINAMO"],
        "makers": ["S1 NO.1 STYLE"],
        "genres": [],
        "source": "fanza",
    }

    config = {
        "classify": {
            "artists": {"WEST": [], "JPN": []},
            "studios": {"WEST": {}, "JPN": {}},
        }
    }

    dest = classify_filename_with_metadata("SONE-446.mp4", config)
    assert dest == "Actors/MINAMO"


@patch("meridian_x.classify.get_jav_metadata")
def test_classify_filename_with_metadata_maker_fallback(mock_get_meta):
    mock_get_meta.return_value = {
        "code": "SONE-446",
        "actresses": [],
        "makers": ["S1 NO.1 STYLE"],
        "genres": [],
        "source": "fanza",
    }

    config = {
        "classify": {
            "artists": {"WEST": [], "JPN": []},
            "studios": {"WEST": {}, "JPN": {}},
        }
    }

    dest = classify_filename_with_metadata("SONE-446.mp4", config)
    assert dest == "S1 NO.1 STYLE"


@patch("meridian_x.classify.get_jav_metadata")
def test_classify_filename_with_metadata_explicit_config_priority(mock_get_meta):
    config = {
        "classify": {
            "artist_folders": ["Dakota Doll"],
            "studio_folders": []
        }
    }

    dest = classify_filename_with_metadata("dakota_doll_scene.mp4", config)
    assert dest == "Actors/Dakota Doll"
    mock_get_meta.assert_not_called()


@patch("meridian_x.classify.get_jav_metadata")
def test_classify_filename_with_metadata_no_lookup(mock_get_meta):
    config = {
        "classify": {
            "artists": {"WEST": [], "JPN": []},
            "studios": {"WEST": {}, "JPN": {}},
        }
    }

    dest = classify_filename_with_metadata("SONE-446.mp4", config, use_metadata=False)
    assert dest == "JPN"
    mock_get_meta.assert_not_called()


@patch("meridian_x.classify.get_west_metadata")
@patch("meridian_x.classify.get_jav_metadata")
def test_classify_filename_with_metadata_west_stashdb(mock_jav_meta, mock_west_meta):
    mock_jav_meta.return_value = {"actresses": [], "makers": []}
    mock_west_meta.return_value = {
        "query_term": "Lily Love",
        "performers": ["Lily Love"],
        "studio": "Vixen",
        "tags": [],
        "source": "stashdb",
    }

    config = {
        "classify": {
            "artists": {"WEST": [], "JPN": []},
            "studios": {"WEST": {}, "JPN": {}},
        }
    }

    dest = classify_filename_with_metadata("Lily.Love.Sample.mp4", config)
    assert dest == "Actors/Lily Love"


@patch("meridian_x.classify.get_west_metadata")
def test_classify_filename_with_metadata_west_studio_fallback(mock_west_meta):
    mock_west_meta.return_value = {
        "query_term": "Random Scene",
        "performers": [],
        "studio": "Vixen",
        "tags": [],
        "source": "stashdb",
    }

    config = {
        "classify": {
            "artists": {"WEST": [], "JPN": []},
            "studios": {"WEST": {}, "JPN": {}},
        }
    }

    dest = classify_filename_with_metadata("Random.Scene.mp4", config)
    assert dest == "Vixen"


@patch("meridian_x.classify.get_west_metadata")
def test_classify_filename_with_metadata_west_no_lookup(mock_west_meta):
    config = {
        "classify": {
            "artists": {"WEST": [], "JPN": []},
            "studios": {"WEST": {}, "JPN": {}},
        }
    }

    dest = classify_filename_with_metadata("Lily.Love.Sample.mp4", config, use_metadata=False)
    assert dest == "West"
    mock_west_meta.assert_not_called()



