"""
Meridian-X Report Module
대상 서버 disk 사용량 + Transmission 토렌트 상태 리포트 (읽기 전용).
"""

import logging
import subprocess
from collections import Counter
from pathlib import Path

from .core import load_config
from .db import MeridianDB
from .remote import run_remote_ssh

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
    res = run_remote_ssh(
        host=remote.get("host", ""),
        command=cmd,
        user=remote.get("user"),
        timeout=60,
    )
    return res.returncode == 0, res.stdout + res.stderr


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


def retention_status(remote: dict, config: dict, db: MeridianDB) -> None:
    """download_history 대비 원격 실제 잔존 영상 생존율 및 Top 배우/스튜디오 리포트."""
    path = remote["path"]
    cmd = (
        f'find "{path}" -maxdepth 4 -type f '
        '\\( -iname "*.mp4" -o -iname "*.mkv" -o -iname "*.avi" -o -iname "*.wmv" -o -iname "*.ts" \\) '
        '-printf "%P\\n"'
    )
    ok, output = _ssh(remote, cmd)
    if not ok:
        logger.error(f"생존율 조회 실패: {output[:200]}")
        return

    rel_paths = [line.strip() for line in output.splitlines() if line.strip()]
    studio_counts: Counter[str] = Counter()
    actor_counts: Counter[str] = Counter()
    prefix_counts: Counter[str] = Counter()
    top_dirs: set[str] = set()
    jpn_actors = set(config.get("classify", {}).get("artists", {}).get("JPN", []))
    west_actors = set(config.get("classify", {}).get("artists", {}).get("WEST", []))
    all_actors = jpn_actors | west_actors
    west_studios = set(config.get("classify", {}).get("studios", {}).get("WEST", {}).keys())

    import re
    for rel in rel_paths:
        parts = rel.split("/")
        top = parts[0]
        if len(parts) > 1:
            top_dirs.add(top)
        if top == "Actors" and len(parts) >= 3:
            actor_counts[parts[1]] += 1
        elif len(parts) >= 2:
            studio_counts[top] += 1
        else:
            studio_counts["(unclassified)"] += 1

        fname = parts[-1].upper()
        m = re.match(r"^([A-Z]{2,6})-\d{2,5}", fname)
        if m and m.group(1) != "FC2":
            prefix_counts[m.group(1)] += 1

    history_ids = db.get_download_history()
    src_counts = Counter(hid.split(":", 1)[0] for hid in history_ids if ":" in hid)
    fc2_hist = sum(1 for hid in history_ids if hid.lower().startswith("onejav:fc2"))
    jav_hist = src_counts["onejav"] - fc2_hist + src_counts["sukebei"]
    west_hist = src_counts["xxxclub"] + src_counts["tgx"]

    fc2_kept = studio_counts["FC2"]
    jpn_kept = studio_counts["JPN"] + sum(c for a, c in actor_counts.items() if a in jpn_actors)
    west_kept = (
        studio_counts["West"]
        + sum(c for s, c in studio_counts.items() if s in west_studios or s.lower() in {w.lower() for w in west_studios})
        + sum(c for a, c in actor_counts.items() if a in west_actors)
    )
    total_kept = len(rel_paths)
    total_hist = len(history_ids)

    def _pct(kept: int, hist: int) -> str:
        return f"{(kept / hist * 100):.1f}%" if hist > 0 else "N/A"

    logger.info(f"  전체 생존율 : {total_kept} / {total_hist} ({_pct(total_kept, total_hist)})")
    logger.info(f"  FC2  생존율 : {fc2_kept} / {fc2_hist} ({_pct(fc2_kept, fc2_hist)})")
    logger.info(f"  JPN  생존율 : {jpn_kept} / {jav_hist} ({_pct(jpn_kept, jav_hist)})")
    logger.info(f"  WEST 생존율 : {west_kept} / {west_hist} ({_pct(west_kept, west_hist)})")

    if studio_counts:
        logger.info("  잔존 Top 스튜디오/카테고리:")
        for name, cnt in studio_counts.most_common(10):
            logger.info(f"    {cnt:>4} files  {name}")

    if actor_counts:
        logger.info("  잔존 Top 배우:")
        for name, cnt in actor_counts.most_common(10):
            logger.info(f"    {cnt:>4} files  {name}")

    # 대소문자 중복 폴더 및 미등록 배우 경고
    lower_map: dict[str, list[str]] = {}
    for d in sorted(top_dirs):
        lower_map.setdefault(d.lower(), []).append(d)
    dup_dirs = [names for names in lower_map.values() if len(names) > 1]
    if dup_dirs:
        logger.warning(f"  대소문자 중복 폴더: {dup_dirs}")

    unlisted_actors = sorted(a for a in actor_counts if a not in all_actors)
    if unlisted_actors:
        logger.warning(f"  미등록 Actors 폴더 ({len(unlisted_actors)}): {unlisted_actors}")

    db.save_retention_stats(dict(actor_counts), dict(studio_counts), dict(prefix_counts))


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

    logger.info("[Retention] 이력 대비 실제 잔존율")
    retention_status(remote, config, MeridianDB())

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
