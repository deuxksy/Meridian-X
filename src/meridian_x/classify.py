"""
Meridian-X Classify Module
원격 파일 분류 (SSH 하이브리드): Python 매칭 로직 + SSH mv
tidy(flatten/정제) 이후, flatten된 파일을 폴더로 분류.
"""

import logging
import re
import subprocess

from .core import load_config

logger = logging.getLogger(__name__)

# JAV 패턴 (영문 3-5자리 + 숫자 3-5자리)
JPN_PATTERN = r"^[A-Z]{3,5}-\d{3,5}[-\.\s]"


def _ssh(remote: dict, cmd: str) -> tuple[bool, str]:
    """SSH 명령 실행. tidy.py와 동일 패턴."""
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


def _list_files(remote: dict, video_extensions: tuple) -> list[str]:
    """원격 path 최상위 영상 파일 목록 (flatten된 상태 가정)."""
    path = remote["path"]
    ext_pattern = " -o ".join(
        f'-iname "*{ext}"' for ext in video_extensions
    )
    cmd = f'find "{path}" -maxdepth 1 -type f \\( {ext_pattern} \\) -printf "%f\\n" | sort'
    ok, output = _ssh(remote, cmd)
    if not ok:
        logger.error(f"파일 목록 조회 실패: {output[:200]}")
        return []
    return [f for f in output.splitlines() if f]


def classify_filename(filename: str, config: dict) -> str:
    """
    파일명 → 목적지 폴더 결정 (순수 Python 매칭, 테스트 가능).
    우선순위: 배우 > 스튜디오 > 장르 > JPN > FC2 > West
    """
    f_lower = filename.lower()
    classify = config.get("classify", {})

    # 1. 배우
    for folder in classify.get("artist_folders", []):
        if folder.lower() in f_lower:
            return folder

    # 2. 스튜디오
    for folder in classify.get("studio_folders", []):
        if folder.lower() in f_lower:
            return folder

    # 3. 장르 (genres 비어있으면 스킵)
    for folder, rules in config.get("genres", {}).items():
        keyword_match = any(kw in f_lower for kw in rules.get("keywords", []))
        prefix_match = any(
            f_lower.startswith(p.lower()) for p in rules.get("prefixes", [])
        )
        if keyword_match or prefix_match:
            return folder

    # 4. JAV 패턴 (원본 filename: 대문자 패턴)
    if re.match(JPN_PATTERN, filename):
        return "JPN"

    # 5. FC2 패턴 (FC2-PPV-*)
    if re.match(r"^FC2", filename, re.IGNORECASE):
        return "FC2"

    # 6. Fallback
    return "West"


def _move_file(remote: dict, filename: str, dest_folder: str, dry_run: bool) -> str:
    """
    SSH로 파일 이동. Returns: 'moved' | 'skip_dup' | 'error'.
    중복 시 원본 삭제 (classify 일관성 유지).
    """
    path = remote["path"]
    src = f"{path}/{filename}"
    dest_dir = f"{path}/{dest_folder}"
    dest = f"{dest_dir}/{filename}"

    if dry_run:
        logger.info(f"  [Dry-run] {filename} -> {dest_folder}/")
        return "moved"

    cmd = f'''
mkdir -p "{dest_dir}"
if [ -f "{dest}" ]; then
    rm -f "{src}"
    echo "SKIP_DUP"
else
    mv "{src}" "{dest}"
    echo "MOVED"
fi
'''
    ok, output = _ssh(remote, cmd)
    if not ok:
        logger.error(f"  [이동 실패] {filename}: {output[:200]}")
        return "error"
    if "SKIP_DUP" in output:
        logger.info(f"  [중복 스킵] {filename} (이미 {dest_folder}에 존재, 원본 삭제)")
        return "skip_dup"
    logger.info(f"  [분류] {filename} -> {dest_folder}/")
    return "moved"


def run(dry_run: bool = False) -> None:
    """원격 파일 분류 메인 실행. tidy 실행 후 호출 권장."""
    config = load_config()
    remote = config.get("remote", {})
    classify = config.get("classify", {})

    if not remote.get("host"):
        logger.error("remote.host not configured in settings.json")
        return

    video_extensions = tuple(classify.get("video_extensions", []))
    if not video_extensions:
        logger.error("classify.video_extensions not configured")
        return

    logger.info("=== Meridian-X Classify Started (Remote SSH) ===")
    logger.info(f"Dry-run: {dry_run}")

    files = _list_files(remote, video_extensions)
    if not files:
        logger.info("분류할 파일 없음 (tidy 실행 후 시도 권장)")
        logger.info("=== Classify Completed ===")
        return

    logger.info(f"대상 파일: {len(files)}개")

    counts = {}
    for filename in files:
        dest = classify_filename(filename, config)
        result = _move_file(remote, filename, dest, dry_run)
        if result == "moved":
            counts[dest] = counts.get(dest, 0) + 1

    summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) or "없음"
    logger.info(f"=== Classify Completed ({summary}) ===")
