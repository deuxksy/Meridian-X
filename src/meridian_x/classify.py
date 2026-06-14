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

# JAV 패턴 (메이커 코드 3-6자리 알파벳/숫자 + 숫자). 숫자 시작(348NTR) 지원
JPN_PATTERN = r"^[A-Z0-9]{3,6}-\d{2,5}[-\.\s]"


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


def _list_folders(remote: dict, exclude: set) -> list[str]:
    """원격 path 하위 폴더 목록 (분류 목적지 폴더 제외, 대소문자 무시). 멀티파트 폴더 분류용."""
    path = remote["path"]
    cmd = f'find "{path}" -maxdepth 1 -mindepth 1 -type d -printf "%f\\n" | sort'
    ok, output = _ssh(remote, cmd)
    if not ok:
        logger.error(f"폴더 목록 조회 실패: {output[:200]}")
        return []
    exclude_lower = {f.lower() for f in exclude}
    return [f for f in output.splitlines() if f and f.lower() not in exclude_lower]


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


def classify_folder(folder_name: str, config: dict) -> str | None:
    """
    폴더명 → 목적지 폴더 결정. 매칭 안 되면 None (분류 건너뜀).
    우선순위: 배우 > 스튜디오 > 장르 > FC2 > JAV 코드. fallback 없음.
    멀티파트 폴더(FC2-PPV-*, SONE-446 등) 통째로 분류.
    """
    f_lower = folder_name.lower()
    classify = config.get("classify", {})

    # 1. 배우
    for folder in classify.get("artist_folders", []):
        if folder.lower() in f_lower:
            return folder

    # 2. 스튜디오
    for folder in classify.get("studio_folders", []):
        if folder.lower() in f_lower:
            return folder

    # 3. 장르
    for folder, rules in config.get("genres", {}).items():
        keyword_match = any(kw in f_lower for kw in rules.get("keywords", []))
        prefix_match = any(
            f_lower.startswith(p.lower()) for p in rules.get("prefixes", [])
        )
        if keyword_match or prefix_match:
            return folder

    # 4. FC2 (FC2-PPV-*, FC2PPV-* 등)
    if re.match(r"^FC2", folder_name, re.IGNORECASE):
        return "FC2"

    # 5. JAV 코드 폴더 (정확한 코드 형태: SONE-446, 348NTR-100)
    if re.match(r"^[A-Z0-9]{3,6}-\d{2,5}$", folder_name, re.IGNORECASE):
        return "JPN"

    return None


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
mkdir -p "{dest_dir}" || {{ echo "MKDIR_FAIL"; exit; }}
if [ -f "{dest}" ]; then
    rm -f "{src}" && echo "SKIP_DUP" || echo "RM_FAIL"
else
    mv "{src}" "{dest}" && echo "MOVED" || echo "MV_FAIL"
fi
'''
    ok, output = _ssh(remote, cmd)
    if not ok or "FAIL" in output:
        logger.error(f"  [이동 실패] {filename}: {output[:200]}")
        return "error"
    if "SKIP_DUP" in output:
        logger.info(f"  [중복 스킵] {filename} (이미 {dest_folder}에 존재, 원본 삭제)")
        return "skip_dup"
    logger.info(f"  [분류] {filename} -> {dest_folder}/")
    return "moved"


def _move_folder(remote: dict, folder_name: str, dest_folder: str, dry_run: bool) -> str:
    """
    SSH로 폴더째 이동 (멀티파트 보존). Returns: 'moved' | 'skip_dup' | 'error'.
    중복 시 건너뜀 (원본 유지, 덮어쓰기 방지).
    """
    path = remote["path"]
    src = f"{path}/{folder_name}"
    dest_dir = f"{path}/{dest_folder}"
    dest = f"{dest_dir}/{folder_name}"

    if dry_run:
        logger.info(f"  [Dry-run 폴더] {folder_name}/ -> {dest_folder}/")
        return "moved"

    cmd = f'''
mkdir -p "{dest_dir}"
if [ -d "{dest}" ]; then
    echo "SKIP_DUP"
else
    mv "{src}" "{dest}" && echo "MOVED" || echo "MV_FAIL"
fi
'''
    ok, output = _ssh(remote, cmd)
    if not ok or "FAIL" in output:
        logger.error(f"  [폴더 이동 실패] {folder_name}: {output[:200]}")
        return "error"
    if "SKIP_DUP" in output:
        logger.info(f"  [중복 스킵 폴더] {folder_name}/ (이미 {dest_folder}에 존재)")
        return "skip_dup"
    logger.info(f"  [폴더 분류] {folder_name}/ -> {dest_folder}/")
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

    # 폴더 분류 (멀티파트 폴더 통째로 이동)
    exclude_folders = {"FC2", "JPN", "West"}
    exclude_folders.update(classify.get("artist_folders", []))
    exclude_folders.update(classify.get("studio_folders", []))
    exclude_folders.update(config.get("genres", {}).keys())

    folders = _list_folders(remote, exclude_folders)
    if folders:
        logger.info(f"대상 폴더: {len(folders)}개")
        folder_counts = {}
        for folder_name in folders:
            dest = classify_folder(folder_name, config)
            if not dest:
                continue
            result = _move_folder(remote, folder_name, dest, dry_run)
            if result == "moved":
                folder_counts[dest] = folder_counts.get(dest, 0) + 1
        if folder_counts:
            fsummary = ", ".join(f"folder:{k}: {v}" for k, v in sorted(folder_counts.items()))
            logger.info(f"폴더 분류: {fsummary}")

    summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) or "없음"
    logger.info(f"=== Classify Completed ({summary}) ===")
