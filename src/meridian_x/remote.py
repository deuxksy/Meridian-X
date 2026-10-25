"""
Meridian-X Remote Execution & Proxy Fetch Module
원격 SSH 및 프록시 Curl 실행 전용 모듈
"""
import logging
import subprocess
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.6.1 Safari/605.1.15"
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


def get_proxies(config: dict) -> Optional[Dict[str, str]]:
    """프록시 설정을 requests proxies dict로 반환. 미설정 시 None.

    config["proxies"] dict 우선, 없으면 config["proxy"] 문자열로 http/https 동일 적용.
    """
    if config.get("proxies"):
        return config["proxies"]
    if config.get("proxy"):
        return {"http": config["proxy"], "https": config["proxy"]}
    return None


def fetch_via_proxy(url: str, config: dict, timeout: int = 15) -> Optional[str]:
    """프록시 경유 GET (텍스트). 미설정 또는 실패 시 None."""
    proxies = get_proxies(config)
    if not proxies:
        return None
    user_agent = config.get("user_agent", DEFAULT_USER_AGENT)
    try:
        resp = requests.get(
            url, headers={"User-Agent": user_agent}, proxies=proxies, timeout=timeout
        )
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.warning(f"fetch_via_proxy failed for {url[:80]}: {e}")
        return None


def download_via_proxy(
    url: str,
    config: dict,
    timeout: int = 30,
    cookies: Optional[Dict[str, str]] = None,
    user_agent: Optional[str] = None,
) -> Optional[bytes]:
    """프록시 경유 GET (바이너리 - torrent metainfo 등). 미설정 또는 실패 시 None.

    cookies/user_agent: FlareSolverr가 발급한 cf_clearance 재사용 시 지정 (UA·egress IP 일치 필수).
    """
    proxies = get_proxies(config)
    if not proxies:
        return None
    user_agent = user_agent or config.get("user_agent", DEFAULT_USER_AGENT)
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": user_agent},
            cookies=cookies,
            proxies=proxies,
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        logger.warning(f"download_via_proxy failed for {url[:80]}: {e}")
        return None


def fetch_via_flaresolverr(url: str, config: dict, timeout: int = 60) -> Optional[dict]:
    """FlareSolverr로 Cloudflare challenge를 통과해 페이지 수신. 미설정 또는 실패 시 None.

    config["flaresolverr"] = {"url": ".../v1", "proxy": "http://gluetun:8888"}
    반환: {"html": str, "user_agent": str, "cookies": {name: value}}
    """
    fs = config.get("flaresolverr") or {}
    if not fs.get("url"):
        return None
    payload = {"cmd": "request.get", "url": url, "maxTimeout": timeout * 1000}
    if fs.get("proxy"):
        payload["proxy"] = {"url": fs["proxy"]}
    try:
        data = requests.post(fs["url"], json=payload, timeout=timeout + 30).json()
        solution = data.get("solution") or {}
        if data.get("status") != "ok" or solution.get("status") != 200:
            logger.warning(
                f"fetch_via_flaresolverr failed for {url[:80]}: "
                f"{data.get('message')} (HTTP {solution.get('status')})"
            )
            return None
        return {
            "html": solution.get("response", ""),
            "user_agent": solution.get("userAgent", ""),
            "cookies": {c["name"]: c["value"] for c in solution.get("cookies", [])},
        }
    except Exception as e:
        logger.warning(f"fetch_via_flaresolverr failed for {url[:80]}: {e}")
        return None


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
