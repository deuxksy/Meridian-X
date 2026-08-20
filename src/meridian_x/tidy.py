"""
Meridian-X Tidy Module
원격 파일 정리: 정크 삭제 → Flatten → 파일명 정리 → 라이브러리 갱신
"""

import logging
import subprocess

import requests

from .remote import run_remote_ssh

logger = logging.getLogger(__name__)


def _ssh(remote: dict, cmd: str, dry_run: bool = False) -> tuple[bool, str]:
    """SSH 명령 실행. dry_run이면 실행하지 않고 로그만 남김. Returns (success, output)."""
    if dry_run:
        logger.info(f"[Dry-run SSH] 실행 생략: {cmd[:200]}")
        return True, ""
    res = run_remote_ssh(
        host=remote.get("host", ""),
        command=cmd,
        user=remote.get("user"),
        timeout=60,
        dry_run=dry_run,
    )
    return res.returncode == 0, res.stdout + res.stderr


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


def _build_exclude_args(exclude_folders: list = None) -> str:
    """find 제외 인자 생성 (대소문자 무시: 분류 폴더의 case-variant도 보호)."""
    if not exclude_folders:
        return ""
    return " ".join(f'-not -iname "{f}"' for f in exclude_folders)


def _compute_exclude_folders(config: dict) -> list[str]:
    """flatten 제외 폴더 산출 (classify 분류 목적지 보호). artists/studios dict 구조 지원."""
    from .classify import compute_exclude_folders
    return compute_exclude_folders(config)


def _video_expr() -> str:
    """영상 확장자 find 표현식."""
    return " -o ".join(f'-iname "*{ext}"' for ext in (".mp4", ".mkv", ".avi", ".wmv"))


def _build_flatten_script(path: str, exclude_args: str = "", size_filter: str = "") -> str:
    """flatten 셸 스크립트 생성 (로컬 테스트 가능하도록 분리)."""
    vexpr = _video_expr()
    return f'''
cd "{path}"
find . -maxdepth 1 -type d -not -name "." -not -name ".." {exclude_args} | sort | while read dir; do
    videos=$(find "$dir" -type f \\( {vexpr} \\) {size_filter} 2>/dev/null)
    video_count=$(echo "$videos" | grep -c .)
    if [ "$video_count" -eq 0 ]; then
        continue
    fi
    # 대소문자 중복 폴더 확인 (자기 자신 제외: 2개 이상 매칭 시 중복)
    folder_name_lower=$(basename "$dir" | tr '[:upper:]' '[:lower:]')
    dup_count=$(ls ./ | grep -icFx "$folder_name_lower")
    if [ "$dup_count" -ge 2 ]; then
        # 중복 폴더는 모든 영상을 루트로 병합. 남은 영상이 있으면 폴더 보존
        echo "$videos" | while read video_file; do
            video_name=$(basename "$video_file")
            if [ ! -f "./$video_name" ]; then
                mv "$video_file" "./$video_name" 2>/dev/null
            fi
        done
        remaining=$(find "$dir" -type f \\( {vexpr} \\) {size_filter} 2>/dev/null | wc -l | tr -d ' ')
        if [ "$remaining" -eq 0 ]; then
            rm -rf "$dir"
            echo "FLATTEN_DUP $(basename "$dir")"
        else
            echo "FLATTEN_DUP_PARTIAL $(basename "$dir")"
        fi
        continue
    fi
    if [ "$video_count" -eq 1 ]; then
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
    else
        # 다중 영상 폴더는 classify 폴더 분류가 처리 (삭제 금지)
        echo "SKIP_MULTIVIDEO $(basename "$dir")"
    fi
done
# 실패 다운로드 잔해 정리: 분류 폴더가 아닌 각 폴더에서 0바이트 stub 파일과 빈 폴더(재귀) 삭제
cleaned_before=$(find . -maxdepth 1 -mindepth 1 -type d {exclude_args} | wc -l)
find . -maxdepth 1 -mindepth 1 -type d {exclude_args} | while read dir; do
    find "$dir" -type f -size 0 -delete 2>/dev/null
    find "$dir" -type d -empty -delete 2>/dev/null
done
cleaned_after=$(find . -maxdepth 1 -mindepth 1 -type d {exclude_args} | wc -l)
echo "FOLDERS_CLEANED=$((cleaned_before - cleaned_after))"
'''


def _build_flatten_probe_script(path: str, exclude_args: str = "", size_filter: str = "") -> str:
    """dry-run용 읽기 전용 프로브: flatten 대상 후보 집계 (변경 없음)."""
    vexpr = _video_expr()
    return f'''
cd "{path}"
find . -maxdepth 1 -type d -not -name "." -not -name ".." {exclude_args} | sort | while read dir; do
    videos=$(find "$dir" -type f \\( {vexpr} \\) {size_filter} 2>/dev/null)
    video_count=$(echo "$videos" | grep -c .)
    if [ "$video_count" -eq 0 ]; then
        continue
    fi
    folder_name_lower=$(basename "$dir" | tr '[:upper:]' '[:lower:]')
    dup_count=$(ls ./ | grep -icFx "$folder_name_lower")
    if [ "$dup_count" -ge 2 ]; then
        echo "CANDIDATE_DUP $(basename "$dir") ($video_count videos)"
    elif [ "$video_count" -eq 1 ]; then
        echo "CANDIDATE $(basename "$dir")"
    else
        echo "SKIP_MULTIVIDEO $(basename "$dir") ($video_count videos)"
    fi
done
'''


def flatten_folders(remote: dict, exclude_folders: list = None, min_size_mb: int = 0, dry_run: bool = False) -> int:
    """SSH로 비디오 1개 폴더를 상위로 이동하고 폴더 삭제. classify 분류 폴더 제외, min_size 미만 광고 mp4는 영상 카운트에서 제외.
    대소문자 중복 폴더는 모든 영상을 루트로 병합 (남은 영상 있으면 보존). 다중 영상 폴더는 건드리지 않음 (classify 폴더 분류가 처리).
    flatten 후 0바이트 stub 파일과 빈 폴더(실패 다운로드 잔해)도 함께 정리."""
    path = remote["path"]
    exclude_args = _build_exclude_args(exclude_folders)
    size_filter = f"-size +{min_size_mb}M" if min_size_mb else ""

    if dry_run:
        ok, output = _ssh(remote, _build_flatten_probe_script(path, exclude_args, size_filter))
        if not ok:
            logger.error(f"[Tidy-2] Flatten 프로브 실패: {output[:200]}")
            return 0
        count = 0
        for line in output.splitlines():
            if line.startswith(("CANDIDATE", "SKIP_MULTIVIDEO")):
                logger.info(f"  [Dry-run] {line}")
            if line.startswith("CANDIDATE "):
                count += 1
        logger.info(f"[Tidy-2] Flatten 후보: {count}개 폴더 (dry-run)")
        return count

    ok, output = _ssh(remote, _build_flatten_script(path, exclude_args, size_filter))
    if not ok:
        logger.error(f"[Tidy-2] Flatten 실패: {output[:200]}")
        return 0

    for line in output.splitlines():
        if line.startswith("FLATTEN_FAIL "):
            logger.error(f"  [Flatten 실패] {line[13:]}")
        elif line.startswith("SKIP_MULTIVIDEO "):
            logger.info(f"  [다중 영상 스킵 - classify 폴더 분류 대상] {line[16:]}")
        elif line.startswith("FLATTEN_DUP_PARTIAL "):
            logger.warning(f"  [중복 병합 부분 완료 - 이름 충돌로 원본 보존] {line[20:]}")

    count = output.count("FLATTEN ")
    dup = output.count("FLATTEN_DUP ")
    skipped = output.count("SKIP_MULTIVIDEO ")
    logger.info(f"[Tidy-2] Flatten: {count}개 폴더 (중복 병합 {dup}, 다중 영상 스킵 {skipped})")

    cleaned = 0
    for line in output.splitlines():
        if line.startswith("FOLDERS_CLEANED="):
            cleaned = int(line.split("=")[1])
    logger.info(f"[Tidy-2] 잔해 폴더 정리: {cleaned}개")
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

    if dry_run:
        cmd = f'''
cd "{path}"
count=0
for f in *; do
    [ ! -f "$f" ] && continue
    {prefix_checks} || continue
    new_name=$(echo "$f" | sed "s/^[^@]*@//")
    if [ "$f" != "$new_name" ] && [ ! -f "$new_name" ]; then
        echo "RENAME $f -> $new_name"
        count=$((count+1))
    fi
done
echo "COUNT=$count"
'''
        ok, output = _ssh(remote, cmd)
        if not ok:
            logger.error(f"[Tidy-3] 파일명 정리 프로브 실패: {output[:200]}")
            return 0
        count = 0
        for line in output.splitlines():
            if line.startswith("RENAME "):
                logger.info(f"  [Dry-run] {line[7:]}")
            if line.startswith("COUNT="):
                count = int(line.split("=")[1])
        logger.info(f"[Tidy-3] 파일명 정리 후보: {count}개 (dry-run)")
        return count

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
    ok, output = _ssh(remote, cmd)
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
    if dry_run:
        logger.info("[Dry-run] 정크 삭제 스킵 (SSH 실행 없음)")
        return 0

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
    exclude = _compute_exclude_folders(config)
    min_size = filters.get("min_file_size_mb", 0)
    flattened = flatten_folders(remote, exclude, min_size_mb=min_size, dry_run=dry_run)

    # 4. 파일명 정리
    logger.info("[Step 4/5] 파일명 정리 (SSH)")
    renamed = clean_filenames(remote, clean_prefixes, dry_run=dry_run)

    # 5. Jellyfin library refresh
    if refresh:
        if dry_run:
            logger.info("[Step 5/5] Jellyfin 라이브러리 갱신 생략 (dry-run)")
        else:
            logger.info("[Step 5/5] Jellyfin 라이브러리 갱신")
            refresh_from_config(config)
    else:
        logger.info("[Step 5/5] Jellyfin 갱신 스킵 (refresh=False)")

    logger.info(f"=== Tidy Completed: 삭제 {jf_deleted}, Flatten {flattened}, 정리 {renamed}, 정크 {junk_deleted} ===")
