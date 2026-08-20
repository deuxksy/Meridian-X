import os
import shutil
import subprocess
from pathlib import Path
import pytest
from meridian_x.core import load_config


def test_load_config_encrypted(tmp_path):
    # Setup sample config
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "settings.json"
    raw_json = '{"sources": {"test": {"enabled": true}}}'
    config_file.write_text(raw_json, encoding="utf-8")

    # Encrypt using sops binary mode if sops is available
    sops_bin = shutil.which("sops")
    key_file = Path.home() / ".config" / "sops" / "age" / "keys.txt"

    if not sops_bin or not key_file.exists():
        pytest.skip("sops binary or age keys.txt not found")

    env = os.environ.copy()
    env["SOPS_AGE_KEY_FILE"] = str(key_file)

    enc_cmd = [
        sops_bin,
        "--encrypt",
        "--age",
        "age1qw643dna4spaup6sr5ap0jf039ncjd54e8ekvrfy6p6x96ys2y4qn5vcsy",
        "--input-type",
        "binary",
        "--output-type",
        "binary",
        str(config_file),
    ]
    res = subprocess.run(enc_cmd, capture_output=True, env=env)
    assert res.returncode == 0, f"Encryption failed: {res.stderr.decode()}"

    config_file.write_bytes(res.stdout)

    # Verify load_config decrypts transparently
    loaded = load_config(config_file)
    assert loaded == {"sources": {"test": {"enabled": True}}}


def test_downloaded_history_integration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from meridian_x.core import load_downloaded_history, save_downloaded_history

    txt_file = tmp_path / "downloaded_history.txt"
    txt_file.write_text("SNOS100\nxxxclub:HASH123\n", encoding="utf-8")

    # Loading should migrate legacy txt into DB and return set
    history = load_downloaded_history(str(txt_file))
    assert history == {"onejav:SNOS100", "xxxclub:HASH123"}

    # Saving additional items updates DB
    save_downloaded_history(str(txt_file), {"onejav:SNOS100", "xxxclub:HASH123", "onejav:SNOS101"})

    history_after = load_downloaded_history(str(txt_file))
    assert history_after == {"onejav:SNOS100", "xxxclub:HASH123", "onejav:SNOS101"}


def test_is_fhd_or_higher():
    from meridian_x.core import is_fhd_or_higher

    # High res passes (FHD / 4K)
    assert is_fhd_or_higher("+++ [FHD] START-591 MINAMO") is True
    assert is_fhd_or_higher("[4K] START-406 MINAMO") is True
    assert is_fhd_or_higher("MIAA-001 1080p BluRay") is True
    assert is_fhd_or_higher("STARS-999 2160P UHD") is True

    # Low res & VR/8K rejected
    assert is_fhd_or_higher("[8KVR] 3DSVR-2009 MINAMO") is False
    assert is_fhd_or_higher("[8K HEVC] 3DSVR-1529 MINAMO") is False
    assert is_fhd_or_higher("[HD/720p] START-284 MINAMO") is False
    assert is_fhd_or_higher("[HD] STARS-412 MINAMO") is False
    assert is_fhd_or_higher("[SD] MIAA-123") is False
    assert is_fhd_or_higher("START-100 480p DVDRip") is False
    assert is_fhd_or_higher("Sample 720p Video") is False

    # Default without explicit resolution tags passes
    assert is_fhd_or_higher("MIAA-001 MINAMO Special") is True
    assert is_fhd_or_higher("") is True


