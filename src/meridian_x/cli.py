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


def main():
    parser = argparse.ArgumentParser(
        description="Meridian-X - 미디어 분류 및 수집 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s transmission           # 전체 source Transmission RPC 전송
  %(prog)s transmission --source onejav  # OneJAV만
  %(prog)s transmission --source xxxclub # XXXClub만
  %(prog)s transmission --dry-run  # 미리보기
  %(prog)s filter                 # 기존 토렌트 파일 필터링 (광고 제외)
  %(prog)s label                  # 기존 토렌트에 메이커 코드 labels 설정
  %(prog)s sync                   # Transmission labels → Jellyfin Tags 동기화
  %(prog)s tidy                   # 원격 파일 정리 (정크삭제→Flatten→파일명정리→갱신)
  %(prog)s classify              # 미디어 파일 분류
  %(prog)s classify --dry-run    # 분류 미리보기
  %(prog)s pipeline              # filter → label → sync → tidy → classify 한 번에
  %(prog)s pipeline --dry-run    # 미리보기
        """
    )
    
    parser.add_argument(
        "command",
        choices=["classify", "filter", "label", "pipeline", "sync", "tidy", "transmission"],
        help="실행할 명령"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 변경 없이 미리보기"
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
        help="수집 source 지정 (onejav, xxxclub). 없으면 전체 실행"
    )

    args = parser.parse_args()
    
    # 로그 파일 위치 출력
    logger.info(f"Log file: {log_path}")
    
    # 명령 실행
    if args.command == "classify":
        from .classify import run as classify_run
        classify_run(dry_run=args.dry_run)

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

        logger.info("=== Pipeline Started: filter → label → sync → tidy → classify ===")

        # 1. filter (광고 파일 제외)
        logger.info("[1/5] Filter")
        if args.dry_run:
            logger.info("[Dry-run] Would filter all torrents")
        else:
            n = tx_client.filter_existing(filters)
            logger.info(f"  Filtered: {n} torrents")

        # 2. label (메이커/배우 labels)
        logger.info("[2/5] Label")
        if args.dry_run:
            logger.info("[Dry-run] Would label all torrents")
        else:
            n = tx_client.label_existing()
            logger.info(f"  Labeled: {n} torrents")

        # 3. sync (Transmission labels → Jellyfin Tags)
        logger.info("[3/5] Sync Transmission → Jellyfin")
        if args.dry_run:
            logger.info("[Dry-run] Would sync tags")
        else:
            n = sync_tags(jf_client, tx_client)
            logger.info(f"  Synced: {n} items")

        # 4. tidy (정크삭제 → Flatten → 파일명정리 → 라이브러리갱신)
        logger.info("[4/5] Tidy")
        tidy_run(dry_run=args.dry_run)

        # 5. classify (배우/스튜디오/장르/JPN/FC2/West 분류)
        logger.info("[5/5] Classify")
        classify_run(dry_run=args.dry_run)

        logger.info("=== Pipeline Completed ===")

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


if __name__ == "__main__":
    main()
