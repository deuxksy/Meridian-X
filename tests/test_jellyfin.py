from unittest.mock import MagicMock, patch
import pytest

from meridian_x.jellyfin import JellyfinClient, sync_tags


@patch.object(JellyfinClient, "_post")
@patch.object(JellyfinClient, "get_item")
def test_update_metadata(mock_get_item, mock_post):
    mock_get_item.return_value = {
        "Id": "item123",
        "Name": "SONE-446",
        "Path": "/data/JPN/SONE-446.mp4",
        "Tags": ["existing_tag"],
        "Studios": [],
        "Genres": [],
        "People": [],
        "NullField": None,
    }

    client = JellyfinClient("http://localhost:8096", "test_key")
    metadata = {
        "actresses": ["MINAMO"],
        "makers": ["S1 NO.1 STYLE"],
        "genres": ["単体作品"],
    }

    ok = client.update_metadata("item123", metadata)
    assert ok is True
    mock_post.assert_called_once()
    posted_payload = mock_post.call_args[0][1]
    assert posted_payload["Genres"] == ["単体作品"]
    assert posted_payload["Studios"] == [{"Name": "S1 NO.1 STYLE"}]
    assert posted_payload["People"] == [{"Name": "MINAMO", "Type": "Actor"}]
    assert "minamo" in posted_payload["Tags"]
    assert "s1 no.1 style" in posted_payload["Tags"]
    assert "existing_tag" in posted_payload["Tags"]
    assert "NullField" not in posted_payload


@patch.object(JellyfinClient, "get_item")
def test_update_metadata_not_found(mock_get_item):
    mock_get_item.return_value = None
    client = JellyfinClient("http://localhost:8096", "test_key")
    assert client.update_metadata("invalid_id", {"actresses": ["MINAMO"]}) is False


@patch("meridian_x.jellyfin.get_jav_metadata")
@patch.object(JellyfinClient, "update_metadata")
@patch.object(JellyfinClient, "update_tags")
@patch.object(JellyfinClient, "get_videos")
def test_sync_tags_with_jav_metadata(mock_get_videos, mock_update_tags, mock_update_metadata, mock_get_jav_meta):
    mock_get_videos.return_value = [
        {
            "Id": "item1",
            "Name": "SONE-446",
            "Path": "/data/JPN/SONE-446.mp4",
            "Tags": [],
        }
    ]
    mock_get_jav_meta.return_value = {
        "code": "SONE-446",
        "actresses": ["MINAMO"],
        "makers": ["S1 NO.1 STYLE"],
        "genres": ["単体作品"],
    }
    mock_update_tags.return_value = True

    tx_client = MagicMock()
    tx_client.get_labeled_completed.return_value = {
        "SONE-446": ["jpn", "s1"]
    }

    client = JellyfinClient("http://localhost:8096", "test_key")
    updated = sync_tags(client, tx_client)

    assert updated == 1
    mock_update_metadata.assert_called_once_with(
        "item1",
        {
            "code": "SONE-446",
            "actresses": ["MINAMO"],
            "makers": ["S1 NO.1 STYLE"],
            "genres": ["単体作品"],
        }
    )
    mock_update_tags.assert_called_once_with("item1", ["jpn", "s1"])


@patch.object(JellyfinClient, "_post")
@patch.object(JellyfinClient, "get_item")
def test_update_metadata_west_stashdb(mock_get_item, mock_post):
    mock_get_item.return_value = {
        "Id": "west123",
        "Name": "Vixen.Lily.Love",
        "Path": "/data/West/Vixen.Lily.Love.mp4",
        "Tags": [],
        "Studios": [],
        "Genres": [],
        "People": [],
    }

    client = JellyfinClient("http://localhost:8096", "test_key")
    metadata = {
        "performers": ["Lily Love"],
        "studio": "Vixen",
        "tags": ["Lesbian"],
    }

    ok = client.update_metadata("west123", metadata)
    assert ok is True
    mock_post.assert_called_once()
    posted_payload = mock_post.call_args[0][1]
    assert posted_payload["Studios"] == [{"Name": "Vixen"}]
    assert posted_payload["People"] == [{"Name": "Lily Love", "Type": "Actor"}]
    assert posted_payload["Genres"] == ["Lesbian"]
    assert "lily love" in posted_payload["Tags"]
    assert "vixen" in posted_payload["Tags"]
    assert "lesbian" in posted_payload["Tags"]


@patch("meridian_x.jellyfin.get_west_metadata")
@patch.object(JellyfinClient, "update_metadata")
@patch.object(JellyfinClient, "update_tags")
@patch.object(JellyfinClient, "get_videos")
def test_sync_tags_with_west_metadata(mock_get_videos, mock_update_tags, mock_update_metadata, mock_get_west_meta):
    mock_get_videos.return_value = [
        {
            "Id": "west1",
            "Name": "Vixen.Lily.Love",
            "Path": "/data/West/Vixen.Lily.Love.mp4",
            "Tags": [],
        }
    ]
    mock_get_west_meta.return_value = {
        "query_term": "Vixen Lily Love",
        "performers": ["Lily Love"],
        "studio": "Vixen",
        "tags": ["Lesbian"],
        "source": "stashdb",
    }
    mock_update_tags.return_value = True

    tx_client = MagicMock()
    tx_client.get_labeled_completed.return_value = {
        "Vixen.Lily.Love": ["vixen", "lily love"]
    }

    client = JellyfinClient("http://localhost:8096", "test_key")
    updated = sync_tags(client, tx_client)

    assert updated == 1
    mock_get_west_meta.assert_called_once_with("/data/West/Vixen.Lily.Love.mp4", None)
    mock_update_metadata.assert_called_once_with(
        "west1",
        {
            "query_term": "Vixen Lily Love",
            "performers": ["Lily Love"],
            "studio": "Vixen",
            "tags": ["Lesbian"],
            "source": "stashdb",
        }
    )
    mock_update_tags.assert_called_once_with("west1", ["vixen", "lily love"])


