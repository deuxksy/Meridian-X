"""
Meridian-X Remote Execution & Proxy Fetch Module
원격 SSH 및 프록시 Curl 실행 전용 모듈
"""
import logging
import subprocess
from typing import Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_remote_curl(
    url: str,
    ssh_alias: str = "lt",
    timeout: int = 15,
    headers: Optional[Dict[str, str]] = None,
    follow_redirects: bool = True,
    use_ipv4: bool = True,
) -> str:
    """원격 SSH 프록시(Oracle Cloud KR 등)를 경유하여 curl로 웹 페이지를 안전하게 수집합니다."""
    if not url:
        return ""

    curl_flags = []
    if use_ipv4:
        curl_flags.append("-4")
    curl_flags.append("-sL" if follow_redirects else "-s")
    curl_flags.append(f"--max-time {timeout}")

    # Header configuration
    req_headers = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        req_headers.update(headers)

    for k, v in req_headers.items():
        curl_flags.append(f'-H "{k}: {v}"')

    curl_flags_str = " ".join(curl_flags)
    cmd = [
        "ssh",
        "-o",
        "ConnectTimeout=5",
        ssh_alias,
        f'curl {curl_flags_str} "{url}"',
    ]

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        if res.returncode != 0:
            logger.warning(
                f"fetch_remote_curl non-zero ({res.returncode}) for {url}: {res.stderr.strip()}"
            )
            return ""
        return res.stdout
    except subprocess.TimeoutExpired:
        logger.warning(f"fetch_remote_curl timed out for {url}")
        return ""
    except Exception as e:
        logger.error(f"fetch_remote_curl unexpected error for {url}: {e}")
        return ""


def run_remote_ssh(
    host: str,
    command: str,
    user: Optional[str] = None,
    connect_timeout: int = 5,
    timeout: int = 15,
    dry_run: bool = False,
) -> subprocess.CompletedProcess:
    """NAS 또는 원격 서버에 SSH 명령을 안전하게 실행합니다."""
    target = f"{user}@{host}" if user else host
    if dry_run:
        logger.info(f"[Dry-run SSH] Would run on {target}: {command}")
        return subprocess.CompletedProcess(
            args=["ssh", target, command],
            returncode=0,
            stdout="[Dry-run] OK\n",
            stderr="",
        )

    cmd = [
        "ssh",
        "-o",
        f"ConnectTimeout={connect_timeout}",
        target,
        command,
    ]

    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception as e:
        logger.error(f"run_remote_ssh error on {target}: {e}")
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=1,
            stdout="",
            stderr=str(e),
        )
