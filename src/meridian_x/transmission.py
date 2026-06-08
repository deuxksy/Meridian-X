import base64
import logging
from pathlib import Path
import requests

logger = logging.getLogger(__name__)


class TransmissionClient:
    """Proxmox Transmission RPC 클라이언트"""

    def __init__(self, rpc_url: str, user: str = None, password: str = None,
                 timeout: int = 10, stop_after_download: bool = False):
        """RPC 클라이언트 초기화"""
        self._rpc_url = rpc_url
        self._user = user
        self._password = password
        self._timeout = timeout
        self._stop_after_download = stop_after_download
        self._session_id = None
        self._session = requests.Session()

    def add_torrent(self, metainfo: bytes, download_dir: str = None,
                    labels: list = None, filters: dict = None) -> bool:
        """토렌트 메타데이터(base64 인코딩)를 Transmission에 추가.

        paused로 추가 후 파일 필터링 → unwanted 설정 → 시작.
        """
        base64_metainfo = base64.b64encode(metainfo).decode('utf-8')
        arguments = {"metainfo": base64_metainfo, "paused": True}
        if download_dir:
            arguments["download-dir"] = download_dir

        response = self._rpc_call("torrent-add", arguments)
        if response.get("result") != "success":
            logger.error(f"RPC failed: {response}")
            return False

        result = response.get("arguments", {})

        # 중복이면 필터링 없이 종료
        if "torrent-duplicate" in result:
            logger.info("  [Duplicate]")
            return True

        torrent_added = result.get("torrent-added")
        if not torrent_added:
            return False

        torrent_id = torrent_added["id"]
        torrent_name = torrent_added.get("name", "")

        # labels + seed ratio 설정
        set_args = self._build_torrent_set_args(torrent_id, torrent_name, labels)
        if set_args:
            self._rpc_call("torrent-set", set_args)

        # 파일 필터링
        if filters:
            unwanted = self._get_unwanted_files(torrent_id, filters)
            if unwanted:
                logger.info(f"  [Filter] Excluding {len(unwanted)} files")
                self._rpc_call("torrent-set", {"ids": [torrent_id], "files-unwanted": unwanted})

        # 다운로드 시작
        self._rpc_call("torrent-start", {"ids": [torrent_id]})
        return True

    def add_magnet(self, magnet_url: str, download_dir: str = None,
                    labels: list = None, filters: dict = None) -> bool:
        """magnet URI를 Transmission에 추가 (filename 방식).

        add_torrent과 동일한 흐름: paused → labels → filter → start.
        """
        arguments = {"filename": magnet_url, "paused": True}
        if download_dir:
            arguments["download-dir"] = download_dir

        response = self._rpc_call("torrent-add", arguments)
        if response.get("result") != "success":
            logger.error(f"RPC failed: {response}")
            return False

        result = response.get("arguments", {})

        if "torrent-duplicate" in result:
            logger.info("  [Duplicate]")
            return True

        torrent_added = result.get("torrent-added")
        if not torrent_added:
            return False

        torrent_id = torrent_added["id"]
        torrent_name = torrent_added.get("name", "")

        # labels + seed ratio 설정
        set_args = self._build_torrent_set_args(torrent_id, torrent_name, labels)
        if set_args:
            self._rpc_call("torrent-set", set_args)

        # 파일 필터링
        if filters:
            unwanted = self._get_unwanted_files(torrent_id, filters)
            if unwanted:
                logger.info(f"  [Filter] Excluding {len(unwanted)} files")
                self._rpc_call("torrent-set", {"ids": [torrent_id], "files-unwanted": unwanted})

        # 다운로드 시작
        self._rpc_call("torrent-start", {"ids": [torrent_id]})
        return True

    def filter_existing(self, filters: dict) -> int:
        """전체 토렌트에 파일 필터링 적용. 제외된 토렌트 수 반환."""
        try:
            response = self._rpc_call("torrent-get", {
                "fields": ["id", "name", "files", "fileStats"]
            })
            if response.get("result") != "success":
                return 0

            torrents = response.get("arguments", {}).get("torrents", [])
            filtered_count = 0

            for t in torrents:
                torrent_id = t["id"]
                unwanted = self._filter_files(t["files"], filters)
                if unwanted:
                    logger.info(f"  [Filter] {t['name']}: excluding {len(unwanted)} files")
                    self._rpc_call("torrent-set", {"ids": [torrent_id], "files-unwanted": unwanted})
                    filtered_count += 1

            return filtered_count
        except Exception as e:
            logger.error(f"Failed to filter existing torrents: {e}")
            return 0

    def label_existing(self) -> int:
        """전체 토렌트에 labels 설정 (메이커 + 배우 분리). 적용된 토렌트 수 반환."""
        try:
            response = self._rpc_call("torrent-get", {
                "fields": ["id", "name", "labels"]
            })
            if response.get("result") != "success":
                return 0

            torrents = response.get("arguments", {}).get("torrents", [])
            labeled_count = 0

            for t in torrents:
                torrent_id = t["id"]
                name = t["name"]
                current_labels = t.get("labels", [])

                labels = self._extract_labels_from_name(name)
                if not labels or labels == current_labels:
                    continue

                logger.info(f"  [Label] {name}: {labels}")
                self._rpc_call("torrent-set", {"ids": [torrent_id], "labels": labels})
                labeled_count += 1

            return labeled_count
        except Exception as e:
            logger.error(f"Failed to label existing torrents: {e}")
            return 0

    def _build_torrent_set_args(self, torrent_id: int, torrent_name: str, labels: list = None) -> dict | None:
        """labels + seed ratio를 묶어서 torrent-set 인자 생성. 없으면 None."""
        if labels is None and torrent_name:
            labels = self._extract_labels_from_name(torrent_name)

        args = {"ids": [torrent_id]}
        has_args = False

        if labels:
            args["labels"] = labels
            has_args = True

        if self._stop_after_download:
            args["seedRatioMode"] = 1  # per-torrent
            args["seedRatioLimit"] = 0.0
            has_args = True

        return args if has_args else None

    @staticmethod
    def _extract_labels_from_name(name: str) -> list:
        """토렌트 이름에서 labels를 추출합니다.

        West: ['vixen', 'lily love'] (스튜디오 + 배우)
        JAV:  ['snos'] (메이커 코드만)
        """
        import re
        # West 패턴 감지
        west_match = re.match(
            r'^([A-Za-z]+[0-9]*?)\.\d{2}(?:\.\d{2})?\.(.+?)\.XXX', name
        )
        if west_match:
            studio = west_match.group(1).lower()
            labels = [studio]

            # 배우 이름 추출 (최대 2단어)
            parts = west_match.group(2).split('.')
            _title_words = {'and', 'or', 'the', 'her', 'his', 'with', 'for', 'in', 'on', 'to', 'of', 'a'}
            actresses = []
            for p in parts:
                if (len(p) > 1 and p[0:1].isupper()
                        and p.lower() not in _title_words
                        and not p[0].isdigit()):
                    actresses.append(p)
                    if len(actresses) >= 2:
                        break
            if actresses:
                labels.append(' '.join(actresses).lower())
            return labels

        # JAV 패턴: 메이커 코드
        cleaned = re.sub(r'[-.\s]+', '', name).split('(')[0].rstrip('ch')
        stripped = re.sub(r'^\d+', '', cleaned)
        match = re.match(r'^([A-Z]+)(\d(?=[A-Z]))?', stripped)
        if match:
            return [(match.group(1) + (match.group(2) or '')).lower()]
        return []

    def _get_unwanted_files(self, torrent_id: int, filters: dict) -> list:
        """단일 토렌트의 파일 목록 조회 후 제외 인덱스 반환."""
        try:
            response = self._rpc_call("torrent-get", {
                "ids": [torrent_id],
                "fields": ["files", "fileStats"]
            })
            if response.get("result") != "success":
                return []

            torrents = response.get("arguments", {}).get("torrents", [])
            if not torrents:
                return []

            return self._filter_files(torrents[0]["files"], filters)
        except Exception as e:
            logger.warning(f"  [Filter] Failed to get file list: {e}")
            return []

    def _filter_files(self, files: list, filters: dict) -> list:
        """파일 목록에서 필터 규칙에 맞는 인덱스를 반환합니다."""
        exclude_ext = set(ext.lower() for ext in filters.get("exclude_extensions", []))
        exclude_kw = [kw.lower() for kw in filters.get("exclude_keywords", [])]
        min_size = filters.get("min_file_size_mb", 0) * 1024 * 1024

        unwanted = []
        for i, f in enumerate(files):
            name = Path(f["name"]).name.lower()
            length = f.get("length", 0)

            if Path(name).suffix.lower() in exclude_ext:
                logger.debug(f"  [Filter] Exclude (ext): {f['name']}")
                unwanted.append(i)
                continue
            if any(kw in name for kw in exclude_kw):
                logger.debug(f"  [Filter] Exclude (keyword): {f['name']}")
                unwanted.append(i)
                continue
            if min_size > 0 and length < min_size:
                logger.debug(f"  [Filter] Exclude (size): {f['name']} ({length / 1024 / 1024:.1f}MB)")
                unwanted.append(i)
                continue

        return unwanted

    def _rpc_call(self, method: str, arguments: dict = None, max_retries: int = 3) -> dict:
        """RPC 요청 공통 메서드 (세션 ID 처리)"""
        if arguments is None:
            arguments = {}

        auth = (self._user, self._password) if self._user and self._password else None

        for attempt in range(max_retries):
            headers = {}
            if self._session_id:
                headers["X-Transmission-Session-Id"] = self._session_id
            try:
                response = self._session.post(
                    self._rpc_url,
                    json={"method": method, "arguments": arguments},
                    headers=headers,
                    auth=auth,
                    timeout=self._timeout
                )

                if response.status_code == 409:
                    self._session_id = response.headers.get("X-Transmission-Session-Id")
                    continue

                response.raise_for_status()
                return response.json()

            except requests.RequestException as e:
                logger.warning(f"RPC attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    continue
                raise

        raise ConnectionError(f"RPC failed after {max_retries} attempts")
