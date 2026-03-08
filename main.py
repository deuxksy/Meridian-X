import argparse
import os
import re
import shutil

# ==========================================
# CONFIGURATION
# ==========================================

# 0. 작업 경로
SOURCE_PATH = "/mnt/data2/torrent/complete"      # 원본 소스 + 분류 목적지
WORK_PATH = "/mnt/data2/torrent/complete/tmp"    # 작업용 (평탄화 결과)

# 1. 평탄화 및 정리 대상 폴더 (SOURCE_PATH 하위)
TARGET_DIRS = [
    "prowlarr",
    "whisparr",
    "one",
    "club",
]

# 2. 분류 규칙 (우선순위: 배우 > 장르 > 스튜디오)
# 1차: 배우 이름 (폴더명 = 키워드, 대소문자 구분 없음)
ACTOR_FOLDERS = ["Dakota", "Kate", "Minamo", "Niko"]

# 2차: 장르 (키워드 + 접두사)
GENRE_RULES = {
    "Mini": {
        "keywords": ["mini", "tiny", "petite", "small"],
        "prefixes": ["CAWD-", "PIYO-", "MUKC-"]
    },
    "Massage": {
        "keywords": ["massage"],
        "prefixes": []
    }
}

# 3차: 스튜디오 (폴더명 = 키워드, 대소문자 구분 없음)
STUDIO_FOLDERS = ["WowGirls", "Vixen", "Tushy", "UltraFilms", "FC2"]

# 4차: 지역 분류 (JAV 패턴)
# 패턴: 영문 3-5글자 + "-" + 숫자 3-5자리 (예: YUJ-057.mp4, HEYZO-3820.mp4)
JPN_PATTERN = r"^[A-Z]{3,5}-\d{3,5}[-\.\s]"

# 3. 삭제할 파일 설정
# 주의: 이 키워드가 포함된 영상 파일은 삭제됩니다.
DELETE_KEYWORDS = [
    "sample",
    "trailer",
    "preview",
    "promo",
    "advertisement",
    "commercial",
    "18+游戏大全",
    "996gg.cc",
]
# 이 확장자를 가진 파일은 무조건 삭제됩니다.
DELETE_EXTENSIONS = [".txt", ".url", ".lnk", ".tmp", ".log", ".dat", ".html", ".nfo"]

# 4. 파일명에서 제거할 광고 문구 (접두사 등)
CLEAN_PREFIXES = ["hhd800.com@"]

# 5. 관리 대상 영상 확장자
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".wmv", ".mov", ".ts", ".m4v")

# 6. 권한 설정
DIR_PERMISSION = 0o755  # drwxr-xr-x
FILE_PERMISSION = 0o644  # -rw-r--r--


# ==========================================
# FUNCTIONS
# ==========================================


def set_permissions(target_dir, dry_run=False):
    """
    DLNA 서버가 접근 가능하도록 디렉토리와 파일의 권한을 설정합니다.
    """
    if not os.path.exists(target_dir):
        return

    if dry_run:
        print(f"[Dry-run] Would set permissions for: {target_dir} ...")
    else:
        print(f"Setting permissions for: {target_dir} ...")

    for root, dirs, files in os.walk(target_dir):
        # 디렉토리 권한 설정
        if dry_run:
            print(f"  [Dry-run] Would chmod dir: {root}")
        else:
            try:
                os.chmod(root, DIR_PERMISSION)
            except Exception as e:
                print(f"  [Error chmod Dir] {root}: {e}")

        # 파일 권한 설정
        for f in files:
            file_path = os.path.join(root, f)
            if dry_run:
                print(f"  [Dry-run] Would chmod file: {file_path}")
            else:
                try:
                    os.chmod(file_path, FILE_PERMISSION)
                except Exception as e:
                    print(f"  [Error chmod File] {file_path}: {e}")


def is_video(filename):
    return filename.lower().endswith(VIDEO_EXTENSIONS)


def clean_and_flatten(target_dir, dry_run=False):
    """
    1. 불필요한 파일 삭제 (SOURCE_PATH)
    2. 파일명 광고 문구 제거
    3. 영상 파일을 WORK_PATH 루트로 이동 (Flatten)
    4. 빈 폴더 삭제
    """
    source_dir = os.path.join(SOURCE_PATH, target_dir)
    if not os.path.exists(source_dir):
        return

    # WORK_PATH가 없으면 생성
    if not os.path.exists(WORK_PATH):
        if dry_run:
            print(f"[Dry-run] Would create work directory: {WORK_PATH}")
        else:
            os.makedirs(WORK_PATH)

    if dry_run:
        print(f"[Dry-run] Would process directory: {target_dir} ...")
    else:
        print(f"Processing directory: {target_dir} ...")

    # Top-down=False로 설정하여 하위 디렉토리부터 처리 (빈 폴더 삭제 용이)
    for root, dirs, files in os.walk(source_dir, topdown=False):
        for filename in files:
            file_path = os.path.join(root, filename)
            f_lower = filename.lower()

            # A. 삭제 로직
            should_delete = False
            # 확장자로 삭제 (정확히 끝나는 것만)
            if any(f_lower.endswith(ext) for ext in DELETE_EXTENSIONS):
                should_delete = True
            # 키워드로 삭제 (파일명에 포함된 경우)
            elif any(kw in f_lower for kw in DELETE_KEYWORDS):
                should_delete = True

            if should_delete:
                if dry_run:
                    print(f"  [Dry-run] Would delete: {filename}")
                else:
                    try:
                        os.remove(file_path)
                        print(f"  [Deleted] {filename}")
                    except Exception as e:
                        print(f"  [Error Deleting] {filename}: {e}")
                continue

            # B. 영상 파일이 아니면 건너뜀 (이미지 등 남은 파일 보존)
            if not is_video(filename):
                continue

            # C. 파일명 정리 (Prefix 제거)
            new_filename = filename
            for prefix in CLEAN_PREFIXES:
                if new_filename.startswith(prefix):
                    new_filename = new_filename.replace(prefix, "", 1)

            # D. 파일 이동 (Flatten: SOURCE_PATH → WORK_PATH 루트)
            new_path = os.path.join(WORK_PATH, new_filename)

            if os.path.exists(new_path):
                # WORK_PATH에 이미 파일이 있으면 (중복), 원본 삭제
                if dry_run:
                    print(
                        f"  [Dry-run] Would delete duplicate: {filename} (File exists in work path)"
                    )
                else:
                    try:
                        os.remove(file_path)
                        print(
                            f"  [Deleted Duplicate] {filename} (File exists in work path)"
                        )
                    except Exception as e:
                        print(f"  [Error Deleting Duplicate] {filename}: {e}")
            else:
                if dry_run:
                    print(
                        f"  [Dry-run] Would move to work path: {filename} -> {new_filename}"
                    )
                else:
                    try:
                        shutil.move(file_path, new_path)
                        print(f"  [Moved to work path] {filename} -> {new_filename}")
                    except Exception as e:
                        print(f"  [Error Moving] {filename}: {e}")

        # 빈 폴더 삭제 (루트 제외)
        if root != source_dir:
            if not os.listdir(root):
                if dry_run:
                    print(f"  [Dry-run] Would remove directory: {root}")
                else:
                    try:
                        os.rmdir(root)
                        print(f"  [Removed Dir] {root}")
                    except Exception as e:
                        print(f"  [Error Removing Dir] {root}: {e}")


def sort_specials(dry_run=False):
    """
    우선순위별 파일 분류 (WORK_PATH → SOURCE_PATH)
    1차: 배우 > 2차: 장르 > 3차: 스튜디오
    """
    if dry_run:
        print("\n[Dry-run] Would sort by category...")
    else:
        print("\nSorting by category...")

    # WORK_PATH가 없으면 종료
    if not os.path.exists(WORK_PATH):
        print(f"  [Warning] Work path does not exist: {WORK_PATH}")
        return

    # WORK_PATH의 파일 목록 수집
    files_to_process = []
    for filename in os.listdir(WORK_PATH):
        file_path = os.path.join(WORK_PATH, filename)
        if os.path.isfile(file_path) and is_video(filename):
            files_to_process.append(filename)

    # 각 파일에 대해 분류 시도
    for filename in files_to_process:
        f_lower = filename.lower()
        file_path = os.path.join(WORK_PATH, filename)
        
        # 1차: 배우 이름으로 분류
        matched = False
        for folder in ACTOR_FOLDERS:
            if folder.lower() in f_lower:
                dest_dir = os.path.join(SOURCE_PATH, folder)
                if not os.path.exists(dest_dir):
                    if not dry_run:
                        os.makedirs(dest_dir)
                    else:
                        print(f"  [Dry-run] Would create directory: {dest_dir}")
                
                new_path = os.path.join(dest_dir, filename)
                if os.path.exists(new_path):
                    print(f"  [Skipped] {filename} (Already exists in {folder})")
                else:
                    if dry_run:
                        print(f"  [Dry-run] Would sort to {folder}: {filename} (Actor)")
                    else:
                        try:
                            shutil.move(file_path, new_path)
                            print(f"  [Sorted to {folder}] {filename} (Actor)")
                        except Exception as e:
                            print(f"  [Error Sorting] {filename}: {e}")
                matched = True
                break
        
        if matched:
            continue

        # 2차: 장르로 분류 (키워드 + 접두사)
        for folder, rules in GENRE_RULES.items():
            # 키워드 체크
            keyword_match = any(kw in f_lower for kw in rules["keywords"])
            # 접두사 체크
            prefix_match = any(f_lower.startswith(prefix.lower()) for prefix in rules["prefixes"])
            
            if keyword_match or prefix_match:
                dest_dir = os.path.join(SOURCE_PATH, folder)
                if not os.path.exists(dest_dir):
                    if not dry_run:
                        os.makedirs(dest_dir)
                    else:
                        print(f"  [Dry-run] Would create directory: {dest_dir}")
                
                new_path = os.path.join(dest_dir, filename)
                if os.path.exists(new_path):
                    print(f"  [Skipped] {filename} (Already exists in {folder})")
                else:
                    match_type = "Prefix" if prefix_match else "Keyword"
                    if dry_run:
                        print(f"  [Dry-run] Would sort to {folder}: {filename} (Genre - {match_type})")
                    else:
                        try:
                            shutil.move(file_path, new_path)
                            print(f"  [Sorted to {folder}] {filename} (Genre - {match_type})")
                        except Exception as e:
                            print(f"  [Error Sorting] {filename}: {e}")
                matched = True
                break
        
        if matched:
            continue

        # 3차: 스튜디오로 분류
        for folder in STUDIO_FOLDERS:
            if folder.lower() in f_lower:
                dest_dir = os.path.join(SOURCE_PATH, folder)
                if not os.path.exists(dest_dir):
                    if not dry_run:
                        os.makedirs(dest_dir)
                    else:
                        print(f"  [Dry-run] Would create directory: {dest_dir}")
                
                new_path = os.path.join(dest_dir, filename)
                if os.path.exists(new_path):
                    print(f"  [Skipped] {filename} (Already exists in {folder})")
                else:
                    if dry_run:
                        print(f"  [Dry-run] Would sort to {folder}: {filename} (Studio)")
                    else:
                        try:
                            shutil.move(file_path, new_path)
                            print(f"  [Sorted to {folder}] {filename} (Studio)")
                        except Exception as e:
                            print(f"  [Error Sorting] {filename}: {e}")
                matched = True
                break
        
        # 4차: 지역 분류 (JAV 패턴)
        if not matched:
            # JPN 패턴 매칭 (예: YUJ-057.mp4)
            if re.match(JPN_PATTERN, filename):
                dest_dir = os.path.join(SOURCE_PATH, "JPN")
                if not os.path.exists(dest_dir):
                    if not dry_run:
                        os.makedirs(dest_dir)
                    else:
                        print(f"  [Dry-run] Would create directory: {dest_dir}")
                
                new_path = os.path.join(dest_dir, filename)
                if os.path.exists(new_path):
                    print(f"  [Skipped] {filename} (Already exists in JPN)")
                else:
                    if dry_run:
                        print(f"  [Dry-run] Would sort to JPN: {filename} (Region - JAV Pattern)")
                    else:
                        try:
                            shutil.move(file_path, new_path)
                            print(f"  [Sorted to JPN] {filename} (Region - JAV Pattern)")
                        except Exception as e:
                            print(f"  [Error Sorting] {filename}: {e}")
                matched = True

        # 5차: 서양권 분류 (나머지 영상 파일)
        if not matched:
            dest_dir = os.path.join(SOURCE_PATH, "West")
            if not os.path.exists(dest_dir):
                if not dry_run:
                    os.makedirs(dest_dir)
                else:
                    print(f"  [Dry-run] Would create directory: {dest_dir}")
            
            new_path = os.path.join(dest_dir, filename)
            if os.path.exists(new_path):
                print(f"  [Skipped] {filename} (Already exists in West)")
            else:
                if dry_run:
                    print(f"  [Dry-run] Would sort to West: {filename} (Region - Western)")
                else:
                    try:
                        shutil.move(file_path, new_path)
                        print(f"  [Sorted to West] {filename} (Region - Western)")
                    except Exception as e:
                        print(f"  [Error Sorting] {filename}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Media Organizer - Clean, flatten, and organize media files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making any changes",
    )
    args = parser.parse_args()

    dry_run = args.dry_run

    print("=== Media Organizer Started ===")
    if dry_run:
        print("[Dry-run mode enabled - no actual changes will be made]")
        print()

    # 1. 각 폴더 청소 및 평탄화
    for d in TARGET_DIRS:
        clean_and_flatten(d, dry_run=dry_run)

    # 2. 우선순위별 분류 (배우 > 장르 > 스튜디오)
    sort_specials(dry_run=dry_run)

    # 3. 권한 설정
    if dry_run:
        print("\n[Dry-run] Would apply DLNA permissions...")
    else:
        print("\nApplying DLNA permissions...")
    
    # 분류된 폴더에 권한 설정 (SOURCE_PATH 하위)
    classified_folders = ACTOR_FOLDERS + list(GENRE_RULES.keys()) + STUDIO_FOLDERS + ["JPN", "West"]
    for d in classified_folders:
        dir_path = os.path.join(SOURCE_PATH, d)
        if os.path.exists(dir_path):
            set_permissions(dir_path, dry_run=dry_run)

    if dry_run:
        print("\n=== Dry-run Complete ===")
        print("[No changes were made. Run without --dry-run to apply changes.]")
    else:
        print("\n=== Organization Complete ===")


if __name__ == "__main__":
    main()
