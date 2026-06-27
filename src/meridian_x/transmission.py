import logging
from pathlib import Path
from urllib.parse import urlparse

from transmission_rpc import Client

logger = logging.getLogger(__name__)


class TransmissionClient:
    """Proxmox Transmission RPC 클라이언트 (transmission-rpc 기반)"""

    def __init__(self, rpc_url: str, user: str = None, password: str = None,
                 timeout: int = 10, stop_after_download: bool = False):
        """RPC 클라이언트 초기화. rpc_url을 protocol/host/port/path로 분리하여
        transmission-rpc Client 생성. 409 세션 ID / Basic Auth는 lib가 처리."""
        parsed = urlparse(rpc_url)
        self._client = Client(
            protocol=parsed.scheme or "http",
            host=parsed.hostname or "127.0.0.1",
            port=parsed.port or (443 if parsed.scheme == "https" else 80),
            path=parsed.path or "/transmission/rpc",
            username=user,
            password=password,
            timeout=timeout,
        )
        self._stop_after_download = stop_after_download

    def add_torrent(self, metainfo: bytes, download_dir: str = None,
                    labels: list = None, filters: dict = None) -> bool:
        """토렌트 메타데이터(bytes)를 Transmission에 추가.

        paused로 추가 후 labels + seed ratio + 파일 필터링 적용 → 시작.
        base64 인코딩은 transmission-rpc가 자동 처리.

        중복 토렌트는 lib가 Torrent 객체로 반환하므로 별도 분기 불가.
        labels/filter는 idempotent하여 동일하게 적용해도 무해하다.
        """
        try:
            torrent = self._client.add_torrent(
                metainfo,
                download_dir=download_dir,
                paused=True,
            )
        except Exception as e:
            logger.error(f"RPC failed: {e}")
            return False

        self._apply_torrent_config(torrent.id, torrent.name, labels, filters)
        self._client.start_torrent(torrent.id)
        return True

    def add_magnet(self, magnet_url: str, download_dir: str = None,
                   labels: list = None, filters: dict = None) -> bool:
        """magnet URI를 Transmission에 추가 (filename 방식).

        add_torrent과 동일한 흐름. 단 transmission-rpc는 magnet에서
        paused를 무시할 수 있으나 labels/filter는 동일하게 적용된다.
        """
        try:
            torrent = self._client.add_torrent(
                magnet_url,
                download_dir=download_dir,
                paused=True,
            )
        except Exception as e:
            logger.error(f"RPC failed: {e}")
            return False

        self._apply_torrent_config(torrent.id, torrent.name, labels, filters)
        self._client.start_torrent(torrent.id)
        return True

    def _apply_torrent_config(self, torrent_id: int, torrent_name: str,
                              labels: list, filters: dict) -> None:
        """labels + seed ratio + 파일 필터링을 공통 적용 (add_torrent/add_magnet용)."""
        if labels is None and torrent_name:
            labels = self._extract_labels_from_name(torrent_name)

        # labels + seed ratio를 한 번의 change_torrent로 묶어 전송
        set_kwargs = {}
        if labels:
            set_kwargs["labels"] = labels
        if self._stop_after_download:
            set_kwargs["seed_ratio_mode"] = 1  # per-torrent
            set_kwargs["seed_ratio_limit"] = 0.0
        if set_kwargs:
            self._client.change_torrent(torrent_id, **set_kwargs)

        # 파일 필터링은 파일 목록 조회가 필요하므로 별도
        if filters:
            unwanted = self._get_unwanted_files(torrent_id, filters)
            if unwanted:
                logger.info(f"  [Filter] Excluding {len(unwanted)} files")
                self._client.change_torrent(torrent_id, files_unwanted=unwanted)

    def filter_existing(self, filters: dict) -> int:
        """전체 토렌트에 파일 필터링 적용. 제외된 토렌트 수 반환."""
        try:
            torrents = self._client.get_torrents(
                arguments=["id", "name", "files", "priorities", "wanted"]
            )
            filtered_count = 0

            for t in torrents:
                unwanted = self._filter_files(t.get_files(), filters)
                if unwanted:
                    logger.info(f"  [Filter] {t.name}: excluding {len(unwanted)} files")
                    self._client.change_torrent(t.id, files_unwanted=unwanted)
                    filtered_count += 1

            return filtered_count
        except Exception as e:
            logger.error(f"Failed to filter existing torrents: {e}")
            return 0

    def label_existing(self) -> int:
        """전체 토렌트에 labels 설정 (메이커 + 배우 분리). 적용된 토렌트 수 반환."""
        try:
            torrents = self._client.get_torrents(
                arguments=["id", "name", "labels"]
            )
            labeled_count = 0

            for t in torrents:
                name = t.name
                current_labels = t.labels or []

                labels = self._extract_labels_from_name(name)
                if not labels or labels == current_labels:
                    continue

                logger.info(f"  [Label] {name}: {labels}")
                self._client.change_torrent(t.id, labels=labels)
                labeled_count += 1

            return labeled_count
        except Exception as e:
            logger.error(f"Failed to label existing torrents: {e}")
            return 0

    def get_torrents_status(self) -> list:
        """report용: status/rate/ratio dict 리스트 반환.

        report.py가 raw RPC dict에 의존하던 것을 대체. 키명은 기존과 동일하게
        유지(status/rateDownload/rateUpload/uploadRatio)하여 호출부 변경 최소화.
        status는 lib Status enum(문자열)을 Transmission RPC 정수 코드로 변환하여
        report.py의 TR_STATUS 정수 매핑이 그대로 작동하도록 한다.
        """
        # lib Status enum value(문자열) → Transmission RPC 정수 코드 (RPC spec 고정)
        status_to_int = {
            "stopped": 0, "check pending": 1, "checking": 2,
            "download pending": 3, "downloading": 4,
            "seed pending": 5, "seeding": 6,
        }
        torrents = self._client.get_torrents(
            arguments=["status", "rateDownload", "rateUpload", "uploadRatio"]
        )
        return [
            {
                "status": status_to_int.get(getattr(t.status, "value", t.status), -1),
                "rateDownload": t.rate_download,
                "rateUpload": t.rate_upload,
                "uploadRatio": t.upload_ratio,
            }
            for t in torrents
        ]

    def get_labeled_completed(self) -> dict:
        """jellyfin sync용: {name: labels} (labels 있고 percentDone >= 1.0).

        jellyfin.sync_tags가 raw RPC에 의존하던 것을 대체.
        """
        torrents = self._client.get_torrents(
            arguments=["name", "labels", "percentDone", "status"]
        )
        return {
            t.name: t.labels
            for t in torrents
            if t.labels and t.percent_done >= 1.0
        }

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
            t = self._client.get_torrent(
                torrent_id,
                arguments=["files", "priorities", "wanted"],
            )
            return self._filter_files(t.get_files(), filters)
        except Exception as e:
            logger.warning(f"  [Filter] Failed to get file list: {e}")
            return []

    def _filter_files(self, files: list, filters: dict) -> list:
        """파일 목록에서 필터 규칙에 맞는 인덱스를 반환합니다.

        files: transmission-rpc File 객체 리스트 (name/size 속성).
        반환 인덱스 == File.id (change_torrent의 files_unwanted에 전달 가능).
        """
        exclude_ext = set(ext.lower() for ext in filters.get("exclude_extensions", []))
        exclude_kw = [kw.lower() for kw in filters.get("exclude_keywords", [])]
        min_size = filters.get("min_file_size_mb", 0) * 1024 * 1024

        unwanted = []
        for i, f in enumerate(files):
            name = Path(f.name).name.lower()
            length = f.size

            if Path(name).suffix.lower() in exclude_ext:
                logger.debug(f"  [Filter] Exclude (ext): {f.name}")
                unwanted.append(i)
                continue
            if any(kw in name for kw in exclude_kw):
                logger.debug(f"  [Filter] Exclude (keyword): {f.name}")
                unwanted.append(i)
                continue
            if min_size > 0 and length < min_size:
                logger.debug(f"  [Filter] Exclude (size): {f.name} ({length / 1024 / 1024:.1f}MB)")
                unwanted.append(i)
                continue

        return unwanted
