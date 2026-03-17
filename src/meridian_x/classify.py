"""
Meridian-X Classify Module
미디어 파일 분류 및 정리
"""

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

# ==========================================
# LOAD CONFIGURATION
# ==========================================

def _load_config() -> Dict:
    """
    config/settings.json에서 설정을 로드합니다.
    """
    config_path = Path(__file__).parent.parent.parent / "config" / "settings.json"
    
    if not config_path.exists():
        logger.error(f"Config not found: {config_path}")
        raise FileNotFoundError(f"Config not found: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


# Load config
CONFIG = _load_config()

# ==========================================
# CONFIGURATION
# ==========================================

# Classify settings
CLASSIFY = CONFIG.get("classify", {})
SOURCE_PATH = CLASSIFY.get("source_path", "/mnt/data2/torrent/complete")
WORK_PATH = CLASSIFY.get("work_path", "/mnt/data2/torrent/complete/tmp")
TARGET_DIRS: List[str] = CLASSIFY.get("target_dirs", [])
ACTOR_FOLDERS: List[str] = CLASSIFY.get("actor_folders", [])
STUDIO_FOLDERS: List[str] = CLASSIFY.get("studio_folders", [])
DELETE_KEYWORDS: List[str] = CLASSIFY.get("delete_keywords", [])
DELETE_EXTENSIONS: Tuple[str, ...] = tuple(CLASSIFY.get("delete_extensions", []))
VIDEO_EXTENSIONS: Tuple[str, ...] = tuple(CLASSIFY.get("video_extensions", []))
CLEAN_PREFIXES: List[str] = CLASSIFY.get("clean_prefixes", [])

# Genre rules
GENRE_RULES = CONFIG.get("genres", {})

# JAV pattern
JPN_PATTERN: str = r"^[A-Z]{3,5}-\d{3,5}[-\.\s]"

# Permissions
DIR_PERMISSION: int = 0o755
FILE_PERMISSION: int = 0o644


# ==========================================
# FUNCTIONS
# ==========================================


def set_permissions(target_dir: str, dry_run: bool = False) -> None:
    """
    DLNA 서버가 접근 가능하도록 디렉토리와 파일의 권한을 설정합니다.
    """
    return  # 권한 변경 비활성화
    if not os.path.exists(target_dir):
        return

    if dry_run:
        logger.info(f"[Dry-run] Would set permissions for: {target_dir} ...")
    else:
        logger.info(f"Setting permissions for: {target_dir} ...")

    for root, dirs, files in os.walk(target_dir):
        if dry_run:
            logger.debug(f"  [Dry-run] Would chmod dir: {root}")
        else:
            try:
                os.chmod(root, DIR_PERMISSION)
            except Exception as e:
                logger.error(f"  [Error chmod Dir] {root}: {e}")

        for f in files:
            file_path = Path(root) / f
            if dry_run:
                logger.debug(f"  [Dry-run] Would chmod file: {file_path}")
            else:
                try:
                    os.chmod(file_path, FILE_PERMISSION)
                except Exception as e:
                    logger.error(f"  [Error chmod File] {file_path}: {e}")


def is_video(filename: str) -> bool:
    return filename.lower().endswith(VIDEO_EXTENSIONS)


def clean_and_flatten(target_dir: str, dry_run: bool = False) -> None:
    """
    1. 불필요한 파일 삭제 (SOURCE_PATH)
    2. 파일명 광고 문구 제거
    3. 영상 파일을 WORK_PATH 루트로 이동 (Flatten)
    4. 빈 폴더 삭제
    """
    source_dir = Path(SOURCE_PATH) / target_dir
    if not source_dir.exists():
        return

    work_path = Path(WORK_PATH)
    if not work_path.exists():
        if dry_run:
            logger.info(f"[Dry-run] Would create work directory: {WORK_PATH}")
        else:
            work_path.mkdir(parents=True)

    if dry_run:
        logger.info(f"[Dry-run] Would process directory: {target_dir} ...")
    else:
        logger.info(f"Processing directory: {target_dir} ...")

    for root, dirs, files in os.walk(source_dir, topdown=False):
        for filename in files:
            file_path = Path(root) / filename
            f_lower = filename.lower()

            # A. 삭제 로직
            should_delete = False
            if any(f_lower.endswith(ext) for ext in DELETE_EXTENSIONS):
                should_delete = True
            elif any(kw in f_lower for kw in DELETE_KEYWORDS):
                should_delete = True

            if should_delete:
                if dry_run:
                    logger.info(f"  [Dry-run] Would delete: {filename}")
                else:
                    try:
                        file_path.unlink()
                        logger.info(f"  [Deleted] {filename}")
                    except Exception as e:
                        logger.error(f"  [Error Deleting] {filename}: {e}")
                continue

            # B. 영상 파일이 아니면 건너뜀
            if not is_video(filename):
                continue

            # C. 파일명 광고 접두사 제거
            new_filename = filename
            for prefix in CLEAN_PREFIXES:
                if new_filename.startswith(prefix):
                    new_filename = new_filename.replace(prefix, "", 1)
                    if dry_run:
                        logger.info(f"  [Cleaned] {filename} -> {new_filename}")

            # D. 파일 이동 (Flatten)
            new_path = Path(WORK_PATH) / new_filename

            if new_path.exists():
                if dry_run:
                    logger.info(f"  [Dry-run] Would delete duplicate: {filename}")
                else:
                    try:
                        file_path.unlink()
                        logger.info(f"  [Deleted Duplicate] {filename}")
                    except Exception as e:
                        logger.error(f"  [Error Deleting Duplicate] {filename}: {e}")
            else:
                if dry_run:
                    logger.info(f"  [Dry-run] Would move to work path: {filename}")
                else:
                    try:
                        shutil.move(str(file_path), str(new_path))
                        logger.info(f"  [Moved to work path] {filename}")
                    except Exception as e:
                        logger.error(f"  [Error Moving] {filename}: {e}")

        # 빈 폴더 삭제
        root_path = Path(root)
        if root_path != source_dir:
            if not any(root_path.iterdir()):
                if dry_run:
                    logger.info(f"  [Dry-run] Would remove directory: {root}")
                else:
                    try:
                        root_path.rmdir()
                        logger.info(f"  [Removed Dir] {root}")
                    except Exception as e:
                        logger.error(f"  [Error Removing Dir] {root}: {e}")


def sort_specials(dry_run: bool = False) -> None:
    """
    우선순위별 파일 분류 (WORK_PATH → SOURCE_PATH)
    1차: 배우 > 2차: 장르 > 3차: 스튜디오
    """
    if dry_run:
        logger.info("[Dry-run] Would sort by category...")
    else:
        logger.info("Sorting by category...")

    work_path = Path(WORK_PATH)
    if not work_path.exists():
        logger.warning(f"  [Warning] Work path does not exist: {WORK_PATH}")
        return

    files_to_process: List[str] = []
    for filename in os.listdir(WORK_PATH):
        file_path = Path(WORK_PATH) / filename
        if file_path.is_file() and is_video(filename):
            files_to_process.append(filename)

    for filename in files_to_process:
        f_lower = filename.lower()
        file_path = Path(WORK_PATH) / filename
        
        # 1차: 배우
        matched = False
        for folder in ACTOR_FOLDERS:
            if folder.lower() in f_lower:
                dest_dir = Path(SOURCE_PATH) / folder
                if not dest_dir.exists():
                    if not dry_run:
                        dest_dir.mkdir(parents=True)
                    else:
                        logger.info(f"  [Dry-run] Would create directory: {dest_dir}")
                
                new_path = dest_dir / filename
                if new_path.exists():
                    logger.info(f"  [Skipped] {filename} (Already exists in {folder})")
                else:
                    if dry_run:
                        logger.info(f"  [Dry-run] Would sort to {folder}: {filename} (Actor)")
                    else:
                        try:
                            shutil.move(str(file_path), str(new_path))
                            logger.info(f"  [Sorted to {folder}] {filename} (Actor)")
                        except Exception as e:
                            logger.error(f"  [Error Sorting] {filename}: {e}")
                matched = True
                break
        
        if matched:
            continue

        # 2차: 장르
        for folder, rules in GENRE_RULES.items():
            keyword_match = any(kw in f_lower for kw in rules["keywords"])
            prefix_match = any(f_lower.startswith(prefix.lower()) for prefix in rules["prefixes"])
            
            if keyword_match or prefix_match:
                dest_dir = Path(SOURCE_PATH) / folder
                if not dest_dir.exists():
                    if not dry_run:
                        dest_dir.mkdir(parents=True)
                    else:
                        logger.info(f"  [Dry-run] Would create directory: {dest_dir}")
                
                new_path = dest_dir / filename
                if new_path.exists():
                    logger.info(f"  [Skipped] {filename} (Already exists in {folder})")
                else:
                    if dry_run:
                        logger.info(f"  [Dry-run] Would sort to {folder}: {filename} (Genre)")
                    else:
                        try:
                            shutil.move(str(file_path), str(new_path))
                            logger.info(f"  [Sorted to {folder}] {filename} (Genre)")
                        except Exception as e:
                            logger.error(f"  [Error Sorting] {filename}: {e}")
                matched = True
                break
        
        if matched:
            continue

        # 3차: 스튜디오
        for folder in STUDIO_FOLDERS:
            if folder.lower() in f_lower:
                dest_dir = Path(SOURCE_PATH) / folder
                if not dest_dir.exists():
                    if not dry_run:
                        dest_dir.mkdir(parents=True)
                    else:
                        logger.info(f"  [Dry-run] Would create directory: {dest_dir}")
                
                new_path = dest_dir / filename
                if new_path.exists():
                    logger.info(f"  [Skipped] {filename} (Already exists in {folder})")
                else:
                    if dry_run:
                        logger.info(f"  [Dry-run] Would sort to {folder}: {filename} (Studio)")
                    else:
                        try:
                            shutil.move(str(file_path), str(new_path))
                            logger.info(f"  [Sorted to {folder}] {filename} (Studio)")
                        except Exception as e:
                            logger.error(f"  [Error Sorting] {filename}: {e}")
                matched = True
                break
        
        if matched:
            continue

        # 4차: JAV
        if re.match(JPN_PATTERN, filename):
            dest_dir = Path(SOURCE_PATH) / "JPN"
            if not dest_dir.exists():
                if not dry_run:
                    dest_dir.mkdir(parents=True)
                else:
                    logger.info(f"  [Dry-run] Would create directory: {dest_dir}")
            
            new_path = dest_dir / filename
            if new_path.exists():
                logger.info(f"  [Skipped] {filename} (Already exists in JPN)")
            else:
                if dry_run:
                    logger.info(f"  [Dry-run] Would sort to JPN: {filename}")
                else:
                    try:
                        shutil.move(str(file_path), str(new_path))
                        logger.info(f"  [Sorted to JPN] {filename}")
                    except Exception as e:
                        logger.error(f"  [Error Sorting] {filename}: {e}")


def run(dry_run: bool = False) -> None:
    """
    메인 실행 함수
    """
    logger.info("=== Meridian-X Classify Started ===")
    logger.info(f"Dry-run: {dry_run}")
    logger.info(f"Source: {SOURCE_PATH}")
    logger.info(f"Work: {WORK_PATH}")
    logger.info(f"Genre rules: {len(GENRE_RULES)}")
    
    for target in TARGET_DIRS:
        clean_and_flatten(target, dry_run=dry_run)
    
    sort_specials(dry_run=dry_run)
    
    logger.info("=== Meridian-X Classify Completed ===")
