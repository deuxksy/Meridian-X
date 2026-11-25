from meridian_x import jav_metadata, west_metadata


def test_default_metadata_caches_are_stored_in_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    jav_metadata.load_cache()
    west_metadata.load_cache()

    assert (tmp_path / "data/jav_metadata_cache.db").is_file()
    assert (tmp_path / "data/stashdb_metadata_cache.db").is_file()
    assert not (tmp_path / "logs").exists()
