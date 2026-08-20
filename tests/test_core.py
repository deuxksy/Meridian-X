import os
import shutil
import subprocess
from pathlib import Path
import pytest
from meridian_x.core import (
    load_config,
    extract_page_links,
    is_fhd_or_higher,
    extract_scene_key,
    score_release,
    deduplicate_releases,
)


def test_load_config_plain_json(tmp_path):
    config_file = tmp_path / "settings.json"
    config_file.write_text('{"app": "meridian_x", "sources": {"onejav": {"enabled": true}}}', encoding="utf-8")
    loaded = load_config(config_file)
    assert loaded == {"app": "meridian_x", "sources": {"onejav": {"enabled": True}}}


def test_load_config_not_found(tmp_path):
    missing_file = tmp_path / "non_existent.json"
    with pytest.raises(FileNotFoundError):
        load_config(missing_file)


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


def test_extract_page_links():
    sample_rss = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title><![CDATA[MIAA-001 Sample Title]]></title>
          <link>https://onejav.com/torrent/200GANA3353</link>
          <description><![CDATA[Sample description text]]></description>
        </item>
        <item>
          <title>STARS-999 Another Title</title>
          <link>https://onejav.com/torrent/STARS999</link>
          <description>Simple description</description>
        </item>
      </channel>
    </rss>"""

    links = extract_page_links(sample_rss)
    assert len(links) == 2
    assert links[0]["id"] == "200GANA3353"
    assert links[0]["title"] == "MIAA-001 Sample Title"
    assert links[0]["page_url"] == "https://onejav.com/torrent/200GANA3353"
    assert links[0]["description"] == "Sample description text"

    assert links[1]["id"] == "STARS999"
    assert links[1]["title"] == "STARS-999 Another Title"


def test_is_fhd_or_higher():
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


def test_extract_scene_key():
    # West pattern
    key1 = extract_scene_key("Tiny4K 26 08 06 Hazel Heart XXX 1080p MP4-WRB [XC]")
    assert key1.startswith("west_tiny4k_260806_hazel_heart")

    # JAV pattern
    key2 = extract_scene_key("[FHD] SONE-446 Minamo Special")
    assert key2 == "jav_sone_446"

    key3 = extract_scene_key("ipx 123 1080p")
    assert key3 == "jav_ipx_123"

    # Other general pattern
    key4 = extract_scene_key("Random Video Presentation 2026")
    assert key4.startswith("other_random_video_presentation")


def test_score_release():
    item_1080p_wrb = {"title": "Sample 1080p WRB", "seeders": "25"}
    item_4k_trb = {"title": "Sample 4K TRB", "seeders": "100"}
    item_p2p = {"title": "Sample 720p P2P", "seeders": "10"}

    score1 = score_release(item_1080p_wrb)
    score2 = score_release(item_4k_trb)
    score3 = score_release(item_p2p)

    # 1080p (1000) + WRB (300) + 25 = 1325
    assert score1 == 1325
    # 4K (500) + TRB (200) + 50 (max cap) = 750
    assert score2 == 750
    # Other (100) + P2P (100) + 10 = 210
    assert score3 == 210

    assert score1 > score2 > score3


def test_deduplicate_releases_1080p_and_release_group_priority():
    items = [
        {"id": "tgx:1", "title": "Tiny4K 26 08 06 Hazel Heart XXX 2160p MP4 WRB XC", "seeders": "17"},
        {"id": "tgx:2", "title": "Tiny4K.26.08.06.Hazel.Heart.XXX.1080p.MP4-TRB", "seeders": "5"},
        {"id": "tgx:3", "title": "Tiny4K 26 08 06 Hazel Heart XXX 1080p MP4-WRB [XC]", "seeders": "24"},
        {"id": "tgx:4", "title": "Tiny4K 26 06 25 Violet Moon Critical Hit XXX 2160p MP4-WRB [XC]", "seeders": "10"},
        {"id": "tgx:5", "title": "Tiny4K 26 06 25 Violet Moon Critical Hit XXX 1080p MP4 WRB XC", "seeders": "10"},
        {"id": "sukebei:10", "title": "[4K] START-591 MINAMO", "seeders": "15"},
        {"id": "sukebei:11", "title": "[FHD] START-591 MINAMO", "seeders": "40"},
    ]

    deduped = deduplicate_releases(items)
    assert len(deduped) == 3

    # Hazel Heart: 1080p WRB [XC] wins over 2160p and TRB
    assert deduped[0]["id"] == "tgx:3"
    # Violet Moon: 1080p WRB XC wins over 2160p
    assert deduped[1]["id"] == "tgx:5"
    # JAV START-591: [FHD] wins over [4K]
    assert deduped[2]["id"] == "sukebei:11"



