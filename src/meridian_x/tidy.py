"""
Meridian-X Tidy Module
원격 파일 정리: 정크 삭제 → Flatten → 파일명 정리 → 라이브러리 갱신
"""

import logging
import subprocess

import requests

logger = logging.getLogger(__name__)


def _ssh(remote: dict, cmd: str, dry_run: bool = False) -> tuple[bool, str]:
    """SSH 명령 실행. Returns (success, output)."""
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


def delete_junk_jellyfin(jf_config: dict, filters: dict, dry_run: bool = False) -> int:
    """Jellyfin API로 정크 파일 삭제 (키워드/확장자 기반)."""
    base = jf_config["url"].rstrip('/')
    headers = {"X-Emby-Token": jf_config["api_key"]}
    s = requests.Session()
    s.headers.update(headers)

    keywords = [kw.lower() for kw in filters.get("exclude_keywords", [])]
    extensions = [ext.lower() for ext in filters.get("exclude_extensions", [])]

    # 전체 아이템 조회
    resp = s.get(f"{base}/Items", params={
        "Recursive": "true",
        "Fields": "Path",
        "Limit": 1000,
    })
    items = resp.json().get("Items", [])

    deleted = 0
    for item in items:
        name = item.get("Name", "").lower()
        path = item.get("Path", "").lower()

        should_delete = False
        for kw in keywords:
            if kw in name or kw in path:
                should_delete = True
                break
        if not should_delete:
            for ext in extensions:
                if name.endswith(ext):
                    should_delete = True
                    break

        if should_delete:
            item_id = item["Id"]
            if dry_run:
                logger.info(f"[Dry-run] Jellyfin 정크 삭제 예정: {item['Name']} (ID: {item_id})")
                deleted += 1
            else:
                r = s.delete(f"{base}/Items/{item_id}")
                if r.status_code in (200, 204):
                    logger.info(f"  [삭제] {item['Name']}")
                    deleted += 1

    logger.info(f"[Tidy-1] 정크 삭제: {deleted}개")
    return deleted


def flatten_folders(remote: dict, exclude_folders: list = None, min_size_mb: int = 0, dry_run: bool = False) -> int:
    """SSH로 비디오 1개 폴더를 상위로 이동하고 폴더 삭제. classify 분류 폴더 제외, min_size 미만 광고 mp4는 영상 카운트에서 제외."""
    path = remote["path"]
    exclude_args = ""
    if exclude_folders:
        exclude_args = " ".join(f'-not -name "{f}"' for f in exclude_folders)
    size_filter = f"-size +{min_size_mb}M" if min_size_mb else ""
    cmd = f'''
cd "{path}"
find . -maxdepth 1 -type d -not -name "." -not -name ".." {exclude_args} | sort | while read dir; do
    videos=$(find "$dir" -type f \\( -iname "*.mp4" -o -iname "*.mkv" -o -iname "*.avi" -o -iname "*.wmv" \\) {size_filter} 2>/dev/null)
    video_count=$(echo "$videos" | grep -c .)
    if [ "$video_count" -ge 1 ]; then
    # 중복 폴더 확인 (대소문자 불감정 - 이스케이프 시퀀스 오류 수정)
    folder_name_lower=$(basename "$dir" | tr '[:upper:]' '[:lower:]')
    if ls "./" | grep -qi "^$$folder_name_lower$"; then
        # 중복 폴더는 모든 영상 이동 후 폴더 삭제 (find 명령 포맷팅 개선)
        find "$dir" -type f -iname "*.mp4" -o -iname "*.mkv" -o -iname "*.avi" -o -iname "*.wmv" {size_filter} 2>/dev/null | while read video_file; do
            video_name=$(basename "$video_file")
            if [ ! -f "./$video_name" ]; then
                mv "$video_file" "./$video_name" 2>/dev/null
            fi
        done
        rm -rf "$dir"
        echo "FLATTEN_DUP $(basename "$dir")"
        continue
    fi
        video_file=$(echo "$videos" | head -1)
        video_name=$(basename "$video_file")
        if [ ! -f "./$video_name" ]; then
            if mv "$video_file" "./$video_name" 2>/dev/null; then
                rm -rf "$dir"
                echo "FLATTEN $(basename "$dir")"
            else
                echo "FLATTEN_FAIL $(basename "$dir")"
            fi
        fi
    fi
done
'''
    ok, output = _ssh(remote, cmd, dry_run=dry_run)
    if not ok:
        logger.error(f"[Tidy-2] Flatten 실패: {output[:200]}")
        return 0

    for line in output.splitlines():
        if line.startswith("FLATTEN_FAIL "):
            logger.error(f"  [Flatten 실패] {line[13:]}")

    count = output.count("FLATTEN ")
    logger.info(f"[Tidy-2] Flatten: {count}개 폴더")
    return count


def clean_filenames(remote: dict, prefixes: list, dry_run: bool = False) -> int:
    """SSH로 파일명 광고 접두사 제거."""
    if not prefixes:
        logger.info("[Tidy-3] 파일명 정리: 설정된 prefix 없음, 스킵")
        return 0

    path = remote["path"]
    # 각 prefix에 대해 rename 명령 생성
    prefix_checks = " || ".join(
        f'echo "$f" | grep -q "^{prefix}"' for prefix in prefixes
    )
    cmd = f'''
cd "{path}"
count=0
for f in *; do
    [ ! -f "$f" ] && continue
    {prefix_checks} || continue
    new_name=$(echo "$f" | sed "s/^[^@]*@//")
    if [ "$f" != "$new_name" ] && [ ! -f "$new_name" ]; then
        if mv "$f" "$new_name" 2>/dev/null; then
            echo "RENAME $f -> $new_name"
            count=$((count+1))
        else
            echo "MV_FAIL $f -> $new_name"
        fi
    fi
done
echo "COUNT=$count"
'''
    ok, output = _ssh(remote, cmd, dry_run=dry_run)
    if not ok:
        logger.error(f"[Tidy-3] 파일명 정리 실패: {output[:200]}")
        return 0

    count = 0
    for line in output.splitlines():
        if line.startswith("RENAME "):
            logger.info(f"  [정리] {line[7:]}")
        elif line.startswith("MV_FAIL "):
            logger.error(f"  [이동 실패] {line[8:]}")
        if line.startswith("COUNT="):
            count = int(line.split("=")[1])

    logger.info(f"[Tidy-3] 파일명 정리: {count}개")
    return count


def delete_junk_remote(remote: dict, extensions: list, keywords: list = None, image_delete: bool = False, maxdepth: int = 2, dry_run: bool = False) -> int:
    """SSH로 정크 파일 삭제 (.nfo 등 + 포스터 이미지 + keyword 매칭 광고). 서브폴더 포함."""
    path = remote["path"]
    ext_pattern = " -o ".join(f'-iname "*{ext}"' for ext in extensions)

    parts = [f"find . -maxdepth {maxdepth} -type f \\( {ext_pattern} \\) -delete"]
    if image_delete:
        parts.append(f'find . -maxdepth {maxdepth} -type f \\( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \\) -delete')
    if keywords:
        for kw in keywords:
            parts.append(f'find . -maxdepth {maxdepth} -type f -iname "*{kw}*" -delete')

    cmd = f'''
cd "{path}"
nfo_before=$(find . -maxdepth {maxdepth} -type f | wc -l)
{" && ".join(parts)}
nfo_after=$(find . -maxdepth {maxdepth} -type f | wc -l)
echo "DELETED=$((nfo_before - nfo_after))"
'''
    ok, output = _ssh(remote, cmd, dry_run=dry_run)
    if not ok:
        logger.error(f"[Tidy-3b] 정크 삭제 실패: {output[:200]}")
        return 0

    deleted = 0
    for line in output.splitlines():
        if line.startswith("DELETED="):
            deleted = int(line.split("=")[1])

    logger.info(f"[Tidy-3b] 정크 삭제: {deleted}개")
    return deleted


def run(dry_run: bool = False, refresh: bool = True) -> None:
    """Tidy 메인 실행."""
    from .core import load_config
    from .jellyfin import refresh_from_config

    config = load_config()
    classify = config.get("classify", {})
    jf_config = config.get("jellyfin", {})
    filters = config.get("transmission", {}).get("filters", {})
    remote = config.get("remote", {})
    clean_prefixes = classify.get("clean_prefixes", [])
    delete_extensions = classify.get("delete_extensions", [])

    if not remote.get("host"):
        logger.error("remote.host not configured in settings.json")
        return
    if not jf_config.get("url") or not jf_config.get("api_key"):
        logger.error("jellyfin.url and jellyfin.api_key required")
        return

    logger.info("=== Meridian-X Tidy Started ===")

    if dry_run:
        logger.info("[Dry-run] 미리보기 모드 - 실제 변경 없이 동작 로그만 출력")

    # 1. Jellyfin API로 정크 삭제
    logger.info("[Step 1/5] 정크 파일 삭제 (Jellyfin API)")
    jf_deleted = delete_junk_jellyfin(jf_config, filters, dry_run=dry_run)

    # 2. 정크 삭제 (flatten 전, 서브폴더 포함)
    logger.info("[Step 2/5] 정크 삭제 (SSH, keyword/확장자/이미지)")
    junk_keywords = filters.get("exclude_keywords", [])
    junk_deleted = delete_junk_remote(remote, delete_extensions, keywords=junk_keywords, image_delete=True, maxdepth=2, dry_run=dry_run)

    # 3. 폴더 Flatten (classify 분류 폴더 제외, min_size 미만 광고 mp4 제외)
    logger.info("[Step 3/5] 폴더 Flatten (SSH)")
    exclude = set(classify.get("artist_folders", []) + classify.get("studio_folders", []))
    exclude.update(["JPN", "FC2", "West"])
    exclude.update(config.get("genres", {}).keys())
    min_size = filters.get("min_file_size_mb", 0)
    flattened = flatten_folders(remote, sorted(exclude), min_size_mb=min_size, dry_run=dry_run)

    # 4. 파일명 정리
    logger.info("[Step 4/5] 파일명 정리 (SSH)")
    renamed = clean_filenames(remote, clean_prefixes, dry_run=dry_run)

    # 5. Jellyfin library refresh
    if refresh:
        logger.info("[Step 5/5] Jellyfin 라이브러리 갱신")
        refresh_from_config(config)
    else:
        logger.info("[Step 5/5] Jellyfin 갱신 스킵 (refresh=False)")

    logger.info(f"=== Tidy Completed: 삭제 {jf_deleted}, Flatten {flattened}, 정리 {renamed}, 정크 {junk_deleted} ===")
