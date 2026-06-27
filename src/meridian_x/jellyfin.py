"""
Meridian-X Jellyfin Module
Transmission labels → Jellyfin Tags 동기화
"""

import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


class JellyfinClient:
    """Jellyfin REST API 클라이언트"""

    def __init__(self, base_url: str, api_key: str, timeout: int = 10):
        self._base_url = base_url.rstrip('/')
        self._api_key = api_key
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"X-Emby-Token": api_key})

    def _get(self, path: str, params: dict = None) -> dict:
        resp = self._session.get(
            f"{self._base_url}{path}",
            params=params,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: dict) -> dict:
        resp = self._session.post(
            f"{self._base_url}{path}",
            json=data,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    def refresh_library(self) -> bool:
        """전체 라이브러리 스캔 트리거"""
        try:
            self._post("/Library/Refresh", {})
            logger.info("[Jellyfin] Library refresh triggered")
            return True
        except Exception as e:
            logger.error(f"[Jellyfin] Library refresh failed: {e}")
            return False

    def get_videos(self) -> list:
        """모든 비디오 아이템 조회"""
        items = []
        start = 0
        limit = 200
        while True:
            data = self._get("/Items", {
                "Recursive": "true",
                "IncludeItemTypes": "Video",
                "Fields": "Path,Tags,Genres,Studios,ProviderIds,SortName,People,Overview,DateCreated",
                "StartIndex": start,
                "Limit": limit,
            })
            batch = data.get("Items", [])
            items.extend(batch)
            total = data.get("TotalRecordCount", 0)
            start += limit
            if start >= total:
                break
        return items

    def get_item(self, item_id: str) -> dict | None:
        """단일 아이템 조회 (GET /Items?ids= 방식)

        Fields에 컬렉션 필드 포함 필수 (POST 시 .ToList() null crash 방지).
        """
        try:
            data = self._get("/Items", {
                "ids": item_id,
                "Fields": "Path,Tags,Genres,Studios,ProviderIds,SortName,People,Overview,DateCreated",
            })
            items = data.get("Items", [])
            return items[0] if items else None
        except Exception as e:
            logger.error(f"[Jellyfin] Get item failed for {item_id}: {e}")
            return None

    def update_tags(self, item_id: str, tags: list) -> bool:
        """아이템 Tags 업데이트. 전체 아이템을 GET 후 Tags만 수정해서 POST."""
        try:
            item = self.get_item(item_id)
            if not item:
                return False
            item["Tags"] = tags
            # null 필드 제거 (Jellyfin ArgumentNullException 방지)
            item = {k: v for k, v in item.items() if v is not None}
            self._post(f"/Items/{item_id}", item)
            return True
        except Exception as e:
            logger.error(f"[Jellyfin] Update tags failed for {item_id}: {e}")
            return False


def _match_name(torrent_name: str, jellyfin_path: str) -> bool:
    """토렌트 이름과 Jellyfin 파일 경로 매칭.

    토렌트 이름이 파일 경로에 포함되면 매칭.
    """
    filename = Path(jellyfin_path).stem
    return torrent_name in filename or filename in torrent_name


def sync_tags(jellyfin: JellyfinClient, transmission_client) -> int:
    """Transmission labels → Jellyfin Tags 동기화.

    Returns: 업데이트된 아이템 수
"""
    # 1. Transmission: 완료된 토렌트 + labels
    resp = transmission_client._rpc_call("torrent-get", {
        "fields": ["id", "name", "labels", "percentDone", "status"]
    })
    torrents = resp.get("arguments", {}).get("torrents", [])

    # labels 있는 완료 토렌트만 필터
    labeled = {
        t["name"]: t["labels"]
        for t in torrents
        if t.get("labels") and t["percentDone"] >= 1.0
    }
    logger.info(f"[Sync] Transmission: {len(labeled)} labeled completed torrents")

    if not labeled:
        logger.info("[Sync] No labeled completed torrents")
        return 0

    # 2. Jellyfin: 모든 비디오
    videos = jellyfin.get_videos()
    path_map = {}
    for v in videos:
        path = v.get("Path", "")
        if path:
            path_map[v["Id"]] = {
                "name": v["Name"],
                "path": path,
                "tags": v.get("Tags", []),
            }
    logger.info(f"[Sync] Jellyfin: {len(path_map)} videos")

    # 3. 매칭 + Tags 업데이트
    updated = 0
    for item_id, info in path_map.items():
        for torrent_name, labels in labeled.items():
            if not _match_name(torrent_name, info["path"]):
                continue

            # 이미 동일 tags면 스킵
            if sorted(info["tags"]) == sorted(labels):
                continue

            ok = jellyfin.update_tags(item_id, labels)
            if ok:
                logger.info(f"  [Sync] {torrent_name}: {labels}")
                updated += 1
            break

    logger.info(f"[Sync] Completed: {updated} items updated")
    return updated


def refresh_from_config(config: dict) -> bool:
    """config에서 jellyfin 설정 읽어 라이브러리 갱신. url/api_key 없으면 스킵 후 False."""
    jf = config.get("jellyfin", {})
    if not jf.get("url") or not jf.get("api_key"):
        logger.warning("[Jellyfin] url/api_key 미설정, 라이브러리 갱신 스킵")
        return False
    client = JellyfinClient(jf["url"], jf["api_key"], jf.get("timeout", 10))
    return client.refresh_library()
