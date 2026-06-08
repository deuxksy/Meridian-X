import base64
import logging
import requests

logger = logging.getLogger(__name__)


class TransmissionClient:
    """Proxmox Transmission RPC 클라이언트"""

    def __init__(self, rpc_url: str, user: str = None, password: str = None, timeout: int = 10):
        """RPC 클라이언트 초기화"""
        self._rpc_url = rpc_url
        self._user = user
        self._password = password
        self._timeout = timeout
        self._session_id = None
        self._session = requests.Session()

    def add_torrent(self, metainfo: bytes, download_dir: str = None) -> bool:
        """토렌트 메타데이터(base64 인코딩)를 Transmission에 추가"""
        base64_metainfo = base64.b64encode(metainfo).decode('utf-8')
        arguments = {"metainfo": base64_metainfo}
        if download_dir:
            arguments["download-dir"] = download_dir

        response = self._rpc_call("torrent-add", arguments)
        if response.get("result") != "success":
            logger.error(f"RPC failed: {response}")
            return False

        result = response.get("arguments", {})
        return "torrent-added" in result or "torrent-duplicate" in result

    def _rpc_call(self, method: str, arguments: dict = None, max_retries: int = 3) -> dict:
        """RPC 요청 공통 메서드 (세션 ID 처리 + 버전 감지)"""
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
