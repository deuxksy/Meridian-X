#!/usr/bin/env python3
"""
Meridian-X
미디어 분류 및 수집 도구
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

# 로그 디렉토리 설정
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 로그 디렉토리: logs/YYMMDD/hhmmss.log
now = datetime.now()
date_dir = LOG_DIR / now.strftime('%y%m%d')
date_dir.mkdir(parents=True, exist_ok=True)
log_path = date_dir / f"{now.strftime('%H%M%S')}.log"

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=str(log_path),
    filemode='a'  # append mode (날짜별 누적)
)

# 콘솔 핸들러 추가
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
logging.getLogger('').addHandler(console)

logger = logging.getLogger(__name__)


def parse_selection_indices(input_str: str, max_count: int) -> list[int]:
    if input_str.lower() == 'all':
        return list(range(1, max_count + 1))
    
    indices = set()
    parts = input_str.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            subparts = part.split('-')
            if len(subparts) == 2 and subparts[0].isdigit() and subparts[1].isdigit():
                start, end = int(subparts[0]), int(subparts[1])
                for i in range(start, end + 1):
                    if 1 <= i <= max_count:
                        indices.add(i)
        elif part.isdigit():
            i = int(part)
            if 1 <= i <= max_count:
                indices.add(i)
    return sorted(list(indices))


def run_search(
    query: str,
    category: str = None,
    source: str = "xxxclub",
    auto: bool = False,
    delay: float = 5.0,
    dry_run: bool = False,
) -> int:
    import time
    from .core import load_config
    from .db import MeridianDB
    from .transmission import TransmissionClient
    from .sources import SOURCES

    config = load_config()

    if not category:
        if source == "sukebei":
            category = "2_2"
        elif source == "xxxclub":
            category = "1080p"
        else:
            category = ""

    logger.info(f"=== Search: query='{query}', category='{category}', source='{source}' ===")

    if source not in SOURCES:
        logger.error(f"Search only supported for sources {list(SOURCES.keys())}, got '{source}'")
        return 0

    src_module = SOURCES[source]
    if not hasattr(src_module, "search"):
        logger.error(f"Search not supported for source '{source}'")
        return 0

    items = src_module.search(query, category=category, config=config)
    if not items:
        logger.info("No items found.")
        return 0

    db = MeridianDB()
    tx_config = config.get("transmission", {})
    tx_client = None
    if not dry_run and tx_config.get("rpc_url"):
        tx_client = TransmissionClient(
            rpc_url=tx_config["rpc_url"],
            user=tx_config.get("rpc_user"),
            password=tx_config.get("rpc_password"),
            timeout=tx_config.get("timeout", 10),
        )

    def _get_magnet(item: dict) -> str | None:
        magnet = item.get("magnet_url")
        if not magnet and hasattr(src_module, "resolve_magnet") and item.get("details_url"):
            magnet = src_module.resolve_magnet(item["details_url"], config=config)
        elif not magnet and hasattr(src_module, "resolve"):
            payload = src_module.resolve(item, config)
            if payload and payload.get("type") == "magnet":
                magnet = payload.get("data")
        return magnet

    added_count = 0
    if auto:
        logger.info(f"Auto mode enabled. Processing {len(items)} items with delay={delay}s...")
        for idx, item in enumerate(items, 1):
            if db.is_downloaded(item["id"]):
                logger.info(f"[{idx}/{len(items)}] Skip already downloaded: {item['title']}")
                continue

            logger.info(f"[{idx}/{len(items)}] Fetching details: {item['title']}")
            magnet = _get_magnet(item)
            if not magnet:
                logger.warning(f"Failed to extract magnet from {item.get('details_url', item.get('id'))}")
                continue

            if dry_run:
                logger.info(f"[Dry-run] Would add magnet: {magnet[:50]}...")
            else:
                if tx_client:
                    tx_client.add_torrent(magnet)
                db.add_download_history([item["id"]])
                logger.info(f"Added to Transmission & DB: {item['title']}")

            added_count += 1
            if idx < len(items) and delay > 0:
                time.sleep(delay)
    else:
        # Interactive mode
        print(f"\nFound {len(items)} items:")
        for idx, item in enumerate(items, 1):
            status = "[Downloaded]" if db.is_downloaded(item["id"]) else "[New]"
            print(f" {idx:2d}. {status} {item['title']} ({item['size']}, S:{item['seeders']} L:{item['leechers']})")

        try:
            user_input = input("\nEnter item numbers to download (e.g. 1,3-5, all, or q to quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            logger.info("Search cancelled.")
            return 0

        if not user_input or user_input.lower() == 'q':
            logger.info("Search cancelled.")
            return 0

        selected_indices = parse_selection_indices(user_input, len(items))
        for idx in selected_indices:
            item = items[idx - 1]
            if db.is_downloaded(item["id"]):
                print(f"Skip downloaded: {item['title']}")
                continue

            print(f"Fetching magnet for: {item['title']}...")
            magnet = _get_magnet(item)
            if not magnet:
                print(f"Failed to fetch magnet for {item['title']}")
                continue

            if dry_run:
                print(f"[Dry-run] Would add: {item['title']}")
            else:
                if tx_client:
                    tx_client.add_torrent(magnet)
                db.add_download_history([item["id"]])
                print(f"Successfully added: {item['title']}")
            added_count += 1

    return added_count



def main():
    parser = argparse.ArgumentParser(
        description="Meridian-X - 미디어 분류 및 수집 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s transmission           # 전체 source Transmission RPC 전송
  %(prog)s transmission --source onejav  # OneJAV만
  %(prog)s transmission --source xxxclub # XXXClub만
  %(prog)s transmission --source sukebei # Sukebei만
  %(prog)s transmission --dry-run  # 미리보기
  %(prog)s filter                 # 기존 토렌트 파일 필터링 (광고 제외)
  %(prog)s label                  # 기존 토렌트에 메이커 코드 labels 설정
  %(prog)s sync                   # Transmission labels → Jellyfin Tags 동기화
  %(prog)s tidy                   # 원격 파일 정리 (정크삭제→Flatten→파일명정리→갱신)
  %(prog)s classify              # 미디어 파일 분류
  %(prog)s classify --dry-run    # 분류 미리보기
  %(prog)s pipeline              # filter → label → sync → tidy → classify 한 번에
  %(prog)s pipeline --dry-run    # 미리보기
  %(prog)s report                # disk 사용량 + Transmission 상태 리포트
  %(prog)s search "MINAMO" --source sukebei # Sukebei 검색
        """
    )
    
    parser.add_argument(
        "command",
        choices=["classify", "filter", "label", "pipeline", "report", "search", "sync", "tidy", "transmission"],
        help="실행할 명령"
    )

    parser.add_argument(
        "query_pos",
        nargs="?",
        default=None,
        help="검색 키워드 (search 전용)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 변경 없이 미리보기"
    )

    parser.add_argument(
        "--no-refresh",
        action="store_true",
        help="Jellyfin 라이브러리 갱신 스킵 (pipeline 전용)"
    )
    
    parser.add_argument(
        "--max-downloads",
        type=int,
        default=30,
        help="최대 다운로드 수 (기본: 30)"
    )
    
    parser.add_argument(
        "--favorite",
        type=str,
        default=None,
        help="OneJAV Favorite URL (없으면 RSS 전체 다운로드)"
    )

    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="수집/검색 source 지정 (onejav, xxxclub, sukebei). transmission은 미지정 시 전체 실행, search는 기본: xxxclub"
    )

    parser.add_argument(
        "--lookup-jav",
        action="store_true",
        help="JPN 폴더 내 파일 JAV 웹 조회를 통한 배우 폴더 2차 분류"
    )

    parser.add_argument(
        "--query", "-q",
        type=str,
        default=None,
        help="검색 키워드 (search 전용)"
    )

    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="검색 카테고리 (기본: xxxclub은 1080p, sukebei는 2_2)"
    )

    parser.add_argument(
        "--auto",
        action="store_true",
        help="자동 검색 다운로드 모드 (지연시간 적용)"
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=5.0,
        help="자동 모드 요청 간 지연 시간(초, 기본: 5.0)"
    )

    args = parser.parse_args()
    
    # 로그 파일 위치 출력
    logger.info(f"Log file: {log_path}")
    
    # 명령 실행
    if args.command == "classify":
        from .classify import run as classify_run
        classify_run(dry_run=args.dry_run, lookup_jav=args.lookup_jav)

    elif args.command == "transmission":
        from .collect import run_transmission
        run_transmission(
            max_count=args.max_downloads,
            source=args.source,
            dry_run=args.dry_run
        )

    elif args.command == "sync":
        from .core import load_config
        from .transmission import TransmissionClient
        from .jellyfin import JellyfinClient, sync_tags
        config = load_config()
        tx_config = config.get("transmission", {})
        jf_config = config.get("jellyfin", {})
        if not tx_config.get("rpc_url"):
            logger.error("transmission.rpc_url not configured")
            return
        if not jf_config.get("url") or not jf_config.get("api_key"):
            logger.error("jellyfin.url and jellyfin.api_key required in settings.json")
            return
        tx_client = TransmissionClient(
            rpc_url=tx_config["rpc_url"],
            user=tx_config.get("rpc_user"),
            password=tx_config.get("rpc_password"),
            timeout=tx_config.get("timeout", 10),
        )
        jf_client = JellyfinClient(
            base_url=jf_config["url"],
            api_key=jf_config["api_key"],
            timeout=jf_config.get("timeout", 10),
        )
        logger.info("=== Sync Transmission → Jellyfin ===")
        count = sync_tags(jf_client, tx_client)
        logger.info(f"=== Sync Completed ({count} items updated) ===")

    elif args.command == "pipeline":
        from .core import load_config
        from .transmission import TransmissionClient
        from .jellyfin import JellyfinClient, sync_tags
        from .tidy import run as tidy_run
        from .classify import run as classify_run

        config = load_config()
        tx_config = config.get("transmission", {})
        jf_config = config.get("jellyfin", {})
        filters = tx_config.get("filters", {})
        stop_after = tx_config.get("stop_after_download", False)

        if not tx_config.get("rpc_url"):
            logger.error("transmission.rpc_url not configured")
            return
        if not jf_config.get("url") or not jf_config.get("api_key"):
            logger.error("jellyfin.url and jellyfin.api_key required in settings.json")
            return

        tx_client = TransmissionClient(
            rpc_url=tx_config["rpc_url"],
            user=tx_config.get("rpc_user"),
            password=tx_config.get("rpc_password"),
            timeout=tx_config.get("timeout", 10),
            stop_after_download=stop_after,
        )
        jf_client = JellyfinClient(
            base_url=jf_config["url"],
            api_key=jf_config["api_key"],
            timeout=jf_config.get("timeout", 10),
        )

        logger.info("=== Pipeline Started: stop → filter → label → sync → tidy → classify ===")

        # 1. stop (수동 추가 포함 기존 토렌트에 다운로드 완료 후 자동 정지 적용)
        logger.info("[1/6] Stop After Download")
        if not stop_after:
            logger.info("  Skipped (transmission.stop_after_download is false)")
        else:
            n = tx_client.stop_after_download_existing(dry_run=args.dry_run)
            if args.dry_run:
                logger.info(f"  [Dry-run] Would set stop on {n} torrents")
            else:
                logger.info(f"  Stop set: {n} torrents")

        # 2. filter (광고 파일 제외)
        logger.info("[2/6] Filter")
        if args.dry_run:
            logger.info("[Dry-run] Would filter all torrents")
        else:
            n = tx_client.filter_existing(filters)
            logger.info(f"  Filtered: {n} torrents")

        # 3. label (메이커/배우 labels)
        logger.info("[3/6] Label")
        if args.dry_run:
            logger.info("[Dry-run] Would label all torrents")
        else:
            n = tx_client.label_existing()
            logger.info(f"  Labeled: {n} torrents")

        # 4. sync (Transmission labels → Jellyfin Tags)
        logger.info("[4/6] Sync Transmission → Jellyfin")
        if args.dry_run:
            logger.info("[Dry-run] Would sync tags")
        else:
            n = sync_tags(jf_client, tx_client)
            logger.info(f"  Synced: {n} items")

        # 5. tidy (정크삭제 → Flatten → 파일명정리; refresh는 pipeline 마지막에 일괄)
        logger.info("[5/6] Tidy")
        tidy_run(dry_run=args.dry_run, refresh=False)

        # 6. classify (배우/스튜디오/장르/JPN/FC2/West 분류)
        logger.info("[6/6] Classify")
        classify_run(dry_run=args.dry_run, refresh=False, lookup_jav=args.lookup_jav)

        # 7. Jellyfin 라이브러리 갱신 (tidy+classify 변경 사항을 한 번에 반영)
        if args.dry_run:
            logger.info("[7/8] Jellyfin 갱신: [Dry-run] Would refresh")
        elif args.no_refresh:
            logger.info("[7/8] Jellyfin 갱신 스킵 (--no-refresh)")
        else:
            from .jellyfin import refresh_from_config
            logger.info("[7/8] Jellyfin Library Refresh")
            refresh_from_config(config)

        # 8. Report (전체 상태 리포트 출력)
        logger.info("[8/8] System Report")
        from .report import run as report_run
        report_run()

        logger.info("=== Pipeline Completed ===")

    elif args.command == "report":
        from .report import run as report_run
        report_run()

    elif args.command == "tidy":
        from .tidy import run as tidy_run
        tidy_run(dry_run=args.dry_run)

    elif args.command == "filter":
        from .transmission import TransmissionClient
        from .core import load_config
        config = load_config()
        tx_config = config.get("transmission", {})
        if not tx_config.get("rpc_url"):
            logger.error("transmission.rpc_url not configured")
            return
        filters = tx_config.get("filters", {})
        client = TransmissionClient(
            rpc_url=tx_config["rpc_url"],
            user=tx_config.get("rpc_user"),
            password=tx_config.get("rpc_password"),
            timeout=tx_config.get("timeout", 10)
        )
        logger.info("=== Filter Existing Torrents ===")
        if args.dry_run:
            logger.info("[Dry-run] Would filter all torrents")
        else:
            count = client.filter_existing(filters)
            logger.info(f"=== Filter Completed ({count} torrents filtered) ===")

    elif args.command == "label":
        from .transmission import TransmissionClient
        from .core import load_config
        config = load_config()
        tx_config = config.get("transmission", {})
        if not tx_config.get("rpc_url"):
            logger.error("transmission.rpc_url not configured")
            return
        client = TransmissionClient(
            rpc_url=tx_config["rpc_url"],
            user=tx_config.get("rpc_user"),
            password=tx_config.get("rpc_password"),
            timeout=tx_config.get("timeout", 10)
        )
        logger.info("=== Label Existing Torrents ===")
        if args.dry_run:
            logger.info("[Dry-run] Would label all torrents")
        else:
            count = client.label_existing()
            logger.info(f"=== Label Completed ({count} torrents labeled) ===")

    elif args.command == "search":
        query = args.query or args.query_pos
        if not query:
            logger.error("Query is required for search command (e.g. meridian search 'MINAMO' or --query 'MINAMO')")
            sys.exit(1)
        source = args.source or "xxxclub"
        run_search(
            query=query,
            category=args.category,
            source=source,
            auto=args.auto,
            delay=args.delay,
            dry_run=args.dry_run
        )



if __name__ == "__main__":
    main()
