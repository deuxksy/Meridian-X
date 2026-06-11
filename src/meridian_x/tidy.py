"""
Meridian-X Tidy Module
원격 파일 정리: 정크 삭제 → Flatten → 파일명 정리 → 라이브러리 갱신
"""

import logging
import subprocess

import requests

logger = logging.getLogger(__name__)


def _ssh(remote: dict, cmd: str) -> tuple[bool, str]:
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


def delete_junk_jellyfin(jf_config: dict, filters: dict) -> int:
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
            r = s.delete(f"{base}/Items/{item_id}")
            if r.status_code in (200, 204):
                logger.info(f"  [삭제] {item['Name']}")
                deleted += 1

    logger.info(f"[Tidy-1] 정크 삭제: {deleted}개")
    return deleted


def flatten_folders(remote: dict) -> int:
    """SSH로 비디오 1개 폴더를 상위로 이동하고 폴더 삭제."""
    path = remote["path"]
    cmd = f'''
cd "{path}"
find . -maxdepth 1 -type d -not -name "." -not -name ".." | sort | while read dir; do
    videos=$(find "$dir" -type f \\( -iname "*.mp4" -o -iname "*.mkv" -o -iname "*.avi" -o -iname "*.wmv" \\) 2>/dev/null)
    video_count=$(echo "$videos" | grep -c .)
    if [ "$video_count" -eq 1 ]; then
        video_file=$(echo "$videos" | head -1)
        video_name=$(basename "$video_file")
        if [ ! -f "./$video_name" ]; then
            mv "$video_file" "./$video_name"
            rm -rf "$dir"
            echo "FLATTEN $(basename "$dir")"
        fi
    fi
done
'''
    ok, output = _ssh(remote, cmd)
    if not ok:
        logger.error(f"[Tidy-2] Flatten 실패: {output[:200]}")
        return 0

    count = output.count("FLATTEN ")
    logger.info(f"[Tidy-2] Flatten: {count}개 폴더")
    return count


def clean_filenames(remote: dict, prefixes: list) -> int:
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
        mv "$f" "$new_name"
        echo "RENAME $f -> $new_name"
        count=$((count+1))
    fi
done
echo "COUNT=$count"
'''
    ok, output = _ssh(remote, cmd)
    if not ok:
        logger.error(f"[Tidy-3] 파일명 정리 실패: {output[:200]}")
        return 0

    count = 0
    for line in output.splitlines():
        if line.startswith("RENAME "):
            logger.info(f"  [정리] {line[7:]}")
        if line.startswith("COUNT="):
            count = int(line.split("=")[1])

    logger.info(f"[Tidy-3] 파일명 정리: {count}개")
    return count


def delete_junk_remote(remote: dict, extensions: list, image_delete: bool = False) -> int:
    """SSH로 정크 파일 삭제 (.nfo 등 + 포스터 이미지)."""
    path = remote["path"]
    ext_pattern = " -o ".join(f'-iname "*{ext}"' for ext in extensions)

    parts = [f"find . -maxdepth 1 -type f \\( {ext_pattern} \\) -delete"]
    if image_delete:
        parts.append('find . -maxdepth 1 -type f \\( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \\) -delete')

    cmd = f'''
cd "{path}"
nfo_before=$(find . -maxdepth 1 -type f | wc -l)
{" && ".join(parts)}
nfo_after=$(find . -maxdepth 1 -type f | wc -l)
echo "DELETED=$((nfo_before - nfo_after))"
'''
    ok, output = _ssh(remote, cmd)
    if not ok:
        logger.error(f"[Tidy-3b] 정크 삭제 실패: {output[:200]}")
        return 0

    deleted = 0
    for line in output.splitlines():
        if line.startswith("DELETED="):
            deleted = int(line.split("=")[1])

    logger.info(f"[Tidy-3b] 정크 삭제: {deleted}개")
    return deleted


def run(dry_run: bool = False) -> None:
    """Tidy 메인 실행."""
    from .core import load_config
    from .jellyfin import JellyfinClient

    config = load_config()
    jf_config = config.get("jellyfin", {})
    filters = config.get("transmission", {}).get("filters", {})
    remote = config.get("remote", {})
    clean_prefixes = config.get("classify", {}).get("clean_prefixes", [])
    delete_extensions = config.get("classify", {}).get("delete_extensions", [])

    if not remote.get("host"):
        logger.error("remote.host not configured in settings.json")
        return
    if not jf_config.get("url") or not jf_config.get("api_key"):
        logger.error("jellyfin.url and jellyfin.api_key required")
        return

    logger.info("=== Meridian-X Tidy Started ===")

    if dry_run:
        logger.info("[Dry-run] 미리보기 모드")
        # TODO: dry-run 시 변경 내용만 출력
        logger.info("=== Tidy Dry-run Completed ===")
        return

    # 1. Jellyfin API로 정크 삭제
    logger.info("[Step 1/4] 정크 파일 삭제 (Jellyfin API)")
    jf_deleted = delete_junk_jellyfin(jf_config, filters)

    # 2. 원격 Flatten
    logger.info("[Step 2/4] 폴더 Flatten (SSH)")
    flattened = flatten_folders(remote)

    # 3. 파일명 정리 + 정크 삭제 (SSH)
    logger.info("[Step 3/4] 파일명 정리 + 정크 삭제 (SSH)")
    renamed = clean_filenames(remote, clean_prefixes)
    junk_deleted = delete_junk_remote(remote, delete_extensions, image_delete=True)

    # 4. Jellyfin library refresh
    logger.info("[Step 4/4] Jellyfin 라이브러리 갱신")
    jf = JellyfinClient(jf_config["url"], jf_config["api_key"], jf_config.get("timeout", 10))
    jf.refresh_library()

    logger.info(f"=== Tidy Completed: 삭제 {jf_deleted}, Flatten {flattened}, 정리 {renamed}, 정크 {junk_deleted} ===")
