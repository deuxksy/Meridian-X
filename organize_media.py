import os
import shutil

# ==========================================
# CONFIGURATION
# ==========================================

# 1. 평탄화 및 정리 대상 폴더 (이 폴더들 내부의 파일을 밖으로 꺼냄)
TARGET_DIRS = [
    "East", "West", "FC2", "Mini", "U", "Only", "Molester", "POV"
]

# 2. 특수 분류 규칙 (조건 만족 시 해당 폴더로 이동)
SPECIAL_RULES = {
    "Mini": {
        # 파일명(소문자)에 포함될 키워드
        "keywords": ["tiny4k", "exxxtrasmall", "petite", "tiny", "pixie", "small"],
        # 파일명(대문자)에 포함될 품번 접두사
        "prefixes": ["CAWD-", "PIYO-", "MUKC-"]
    }
}

# 3. 삭제할 파일 설정
# 주의: 이 키워드가 포함된 영상 파일은 삭제됩니다.
DELETE_KEYWORDS = [
    "sample", "trailer", "preview", "promo", "advertisement", "commercial",
    "18+游戏大全", "996gg.cc"
]
# 이 확장자를 가진 파일은 무조건 삭제됩니다.
DELETE_EXTENSIONS = ['.txt', '.url', '.lnk', '.tmp', '.log', '.dat', '.html', '.nfo']

# 4. 파일명에서 제거할 광고 문구 (접두사 등)
CLEAN_PREFIXES = [
    "hhd800.com@"
]

# 5. 관리 대상 영상 확장자
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.wmv', '.mov', '.ts', '.m4v')

# 6. 권한 설정
DIR_PERMISSION = 0o755  # drwxr-xr-x
FILE_PERMISSION = 0o644 # -rw-r--r--

# ==========================================
# FUNCTIONS
# ==========================================

def set_permissions(target_dir):
    """
    DLNA 서버가 접근 가능하도록 디렉토리와 파일의 권한을 설정합니다.
    """
    if not os.path.exists(target_dir):
        return

    print(f"Setting permissions for: {target_dir} ...")
    for root, dirs, files in os.walk(target_dir):
        # 디렉토리 권한 설정
        try:
            os.chmod(root, DIR_PERMISSION)
        except Exception as e:
            print(f"  [Error chmod Dir] {root}: {e}")

        # 파일 권한 설정
        for f in files:
            file_path = os.path.join(root, f)
            try:
                os.chmod(file_path, FILE_PERMISSION)
            except Exception as e:
                print(f"  [Error chmod File] {file_path}: {e}")

def is_video(filename):
    return filename.lower().endswith(VIDEO_EXTENSIONS)

def clean_and_flatten(target_dir):
    """
    1. 불필요한 파일 삭제
    2. 하위 폴더의 영상을 루트로 이동 (Flatten)
    3. 파일명 광고 문구 제거
    4. 빈 폴더 삭제
    """
    base_path = os.path.abspath(target_dir)
    if not os.path.exists(base_path):
        return

    print(f"Processing directory: {target_dir} ...")

    # Top-down=False로 설정하여 하위 디렉토리부터 처리 (빈 폴더 삭제 용이)
    for root, dirs, files in os.walk(base_path, topdown=False):
        for filename in files:
            file_path = os.path.join(root, filename)
            f_lower = filename.lower()
            
            # A. 삭제 로직
            should_delete = False
            if any(ext in f_lower for ext in DELETE_EXTENSIONS if f_lower.endswith(ext)):
                should_delete = True
            elif any(k in f_lower for k in DELETE_KEYWORDS):
                should_delete = True
            
            if should_delete:
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
            
            # D. 파일 이동/이름변경 (Flatten)
            # 루트가 아닌 곳에 있거나, 이름이 바뀌어야 한다면 이동
            if root != base_path or new_filename != filename:
                new_path = os.path.join(base_path, new_filename)
                
                if os.path.exists(new_path):
                    # 타겟에 이미 파일이 있으면 (중복), 원본이 서브폴더에 있을 경우 삭제
                    if root != base_path:
                        try:
                            os.remove(file_path)
                            print(f"  [Deleted Duplicate] {filename} (File exists in root)")
                        except Exception as e:
                            print(f"  [Error Deleting Duplicate] {filename}: {e}")
                else:
                    try:
                        shutil.move(file_path, new_path)
                        print(f"  [Moved/Renamed] {filename} -> {new_filename}")
                    except Exception as e:
                        print(f"  [Error Moving] {filename}: {e}")

        # 빈 폴더 삭제 (루트 제외)
        if root != base_path:
            if not os.listdir(root):
                try:
                    os.rmdir(root)
                    print(f"  [Removed Dir] {root}")
                except Exception as e:
                    print(f"  [Error Removing Dir] {root}: {e}")

def sort_specials():
    """
    설정된 규칙(SPECIAL_RULES)에 따라 파일을 특정 폴더(예: Mini)로 이동
    """
    print("\nSorting special categories...")
    
    for target_cat, rules in SPECIAL_RULES.items():
        dest_dir = os.path.abspath(target_cat)
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
            
        # 모든 소스 폴더 검색
        for source_cat in TARGET_DIRS:
            source_path = os.path.abspath(source_cat)
            if not os.path.exists(source_path):
                continue
                
            # 소스 폴더 내 파일 검색
            # (위에서 이미 Flatten 되었으므로 루트만 보면 됨)
            for filename in os.listdir(source_path):
                # 이미 타겟 폴더인 경우 건너뜀
                if os.path.abspath(source_path) == dest_dir:
                    continue
                    
                if not is_video(filename):
                    continue
                    
                f_lower = filename.lower()
                f_upper = filename.upper()
                
                is_match = False
                reason = ""
                
                # 키워드 검사
                for k in rules.get("keywords", []):
                    if k in f_lower:
                        is_match = True
                        reason = f"keyword '{k}'"
                        break
                
                # 접두사 검사
                if not is_match:
                    for p in rules.get("prefixes", []):
                        if p in f_upper:
                            is_match = True
                            reason = f"prefix '{p}'"
                            break
                            
                if is_match:
                    old_path = os.path.join(source_path, filename)
                    new_path = os.path.join(dest_dir, filename)
                    
                    if os.path.exists(new_path):
                        print(f"  [Skipped] {filename} (Already exists in {target_cat})")
                    else:
                        try:
                            shutil.move(old_path, new_path)
                            print(f"  [Sorted to {target_cat}] {filename} ({reason})")
                        except Exception as e:
                            print(f"  [Error Sorting] {filename}: {e}")

def main():
    print("=== Media Organizer Started ===")
    
    # 1. 각 폴더 청소 및 평탄화
    for d in TARGET_DIRS:
        clean_and_flatten(d)
        
    # 2. 특수 카테고리(Mini 등) 분류
    sort_specials()

    # 3. 권한 설정 (Movie 폴더 포함 모든 미디어 폴더)
    print("\nApplying DLNA permissions...")
    all_media_dirs = list(set(TARGET_DIRS + ["Movie"]))
    for d in all_media_dirs:
        set_permissions(d)
    
    print("\n=== Organization Complete ===")

if __name__ == "__main__":
    main()
