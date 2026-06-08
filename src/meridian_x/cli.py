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
  %(prog)s classify              # 미디어 파일 분류
  %(prog)s classify --dry-run    # 분류 미리보기
        """
    )
    
    parser.add_argument(
        "command",
        choices=["classify", "filter", "label", "transmission"],
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

    parser.add_argument(
        "--jav-metadata",
        action="store_true",
        help="FANZA API로 JAV 메타데이터 기반 분류"
    )

    args = parser.parse_args()
    
    # 로그 파일 위치 출력
    logger.info(f"Log file: {log_path}")
    
    # 명령 실행
    if args.command == "classify":
        from .classify import run as classify_run
        classify_run(dry_run=args.dry_run, jav_metadata=args.jav_metadata)

    elif args.command == "transmission":
        from .collect import run_transmission
        run_transmission(
            max_count=args.max_downloads,
            source=args.source,
            dry_run=args.dry_run
        )

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
