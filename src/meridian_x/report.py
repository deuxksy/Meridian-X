"""
Meridian-X Report Module
대상 서버 disk 사용량 + Transmission 토렌트 상태 리포트 (읽기 전용).
"""

import logging
import subprocess
from collections import Counter
from pathlib import Path

from .core import load_config

logger = logging.getLogger(__name__)

# Transmission status 코드 → 표시명
TR_STATUS = {
    0: "stopped",
    1: "check-wait",
    2: "checking",
    3: "dl-wait",
    4: "downloading",
    5: "seed-wait",
    6: "seeding",
}


def _ssh(remote: dict, cmd: str) -> tuple[bool, str]:
    """SSH 명령 실행. tidy.py/classify.py와 동일 패턴."""
    try:
        result = subprocess.run(
            [
                "ssh", "-i", remote["ssh_key"],
                "-o", "ConnectTimeout=5",
                "-o", "StrictHostKeyChecking=no",
                f'{remote["user"]}@{remote["host"]}',
                cmd,
            ],
            capture_output=True, text=True, timeout=60,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def _humanize(num: float) -> str:
    """바이트 → 읽기 쉬운 단위 (K/M/G/T/P)."""
    for unit in ["B", "K", "M", "G", "T", "P"]:
        if abs(num) < 1024:
            return f"{num:.0f}{unit}"
        num /= 1024
    return f"{num:.0f}E"


def disk_status(remote: dict) -> None:
    """disk 사용량 리포트: 파일시스템 전체 + complete 하위 폴더별 (크기순)."""
    path = remote["path"]
    parent = str(Path(path).parent)

    # df 1줄 + complete 하위 폴더별 (바이트, 파일수, 폴더명) 크기순 정렬
    cmd = (
        f'echo "===DF==="; df -h "{parent}" | tail -1; '
        f'echo "===DU==="; cd "{path}" && '
        'for d in */; do '
        'b=$(du -sb "$d" 2>/dev/null | cut -f1); '
        'f=$(find "$d" -type f 2>/dev/null | wc -l); '
        'echo "$b $f $d"; '
        'done | sort -rn'
    )
    ok, output = _ssh(remote, cmd)
    if not ok:
        logger.error(f"disk 상태 조회 실패: {output[:200]}")
        return

    df_part, _, du_part = output.partition("===DU===")
    df_line = df_part.replace("===DF===", "").strip()

    # df: filesystem size used avail use% mounted
    parts = df_line.split()
    if len(parts) >= 6:
        logger.info(f"  Filesystem : {parts[0]}")
        logger.info(f"  Size/Used  : {parts[1]} / {parts[2]} ({parts[4]} 사용)")
        logger.info(f"  Available  : {parts[3]}")
        logger.info(f"  Mounted    : {parts[5]}")

    total_bytes = 0
    rows = []
    for line in du_part.splitlines():
        seg = line.split(None, 2)
        if len(seg) < 3:
            continue
        try:
            bytes_val = int(seg[0])
        except ValueError:
            continue
        files = seg[1]
        folder = seg[2].strip()
        total_bytes += bytes_val
        rows.append((bytes_val, files, folder))

    if rows:
        logger.info("  폴더별 (크기순):")
        for bytes_val, files, folder in rows:
            logger.info(f"    {_humanize(bytes_val):>6}  {files:>6} files  {folder}")
        logger.info(f"  TOTAL: {_humanize(total_bytes)}")


def transmission_status(client) -> None:
    """Transmission 토렌트 상태 집계."""
    torrents = client.get_torrents_status()
    total = len(torrents)

    counts = Counter(TR_STATUS.get(t.get("status"), "unknown") for t in torrents)
    total_dl = sum(t.get("rateDownload", 0) for t in torrents)
    total_ul = sum(t.get("rateUpload", 0) for t in torrents)
    ratios = [t.get("uploadRatio", 0) or 0 for t in torrents]
    avg_ratio = sum(ratios) / len(ratios) if ratios else 0

    logger.info(f"  총 토렌트: {total}")
    logger.info("  상태별:")
    for name in [TR_STATUS[s] for s in sorted(TR_STATUS)] + (["unknown"] if counts.get("unknown") else []):
        if counts.get(name):
            logger.info(f"    {name:<12} {counts[name]}")
    logger.info(f"  다운로드 속도: {_humanize(total_dl)}/s")
    logger.info(f"  업로드 속도  : {_humanize(total_ul)}/s")
    logger.info(f"  평균 ratio   : {avg_ratio:.2f}")


def run() -> None:
    """Report 메인 실행: disk + transmission 상태."""
    config = load_config()
    remote = config.get("remote", {})
    tx_config = config.get("transmission", {})

    logger.info("=== Meridian-X Report ===")

    if not remote.get("host"):
        logger.error("remote.host not configured")
        return

    logger.info("[Disk] 원격 disk 사용량")
    disk_status(remote)

    logger.info("[Transmission] 토렌트 상태")
    if not tx_config.get("rpc_url"):
        logger.warning("  transmission.rpc_url not configured, 스킵")
    else:
        from .transmission import TransmissionClient
        client = TransmissionClient(
            rpc_url=tx_config["rpc_url"],
            user=tx_config.get("rpc_user"),
            password=tx_config.get("rpc_password"),
            timeout=tx_config.get("timeout", 10),
        )
        try:
            transmission_status(client)
        except Exception as e:
            logger.error(f"  Transmission 조회 실패: {e}")

    logger.info("=== Report Completed ===")
