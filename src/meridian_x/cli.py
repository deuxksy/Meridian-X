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
  %(prog)s classify              # 미디어 파일 분류
  %(prog)s classify --dry-run    # 분류 미리보기
  %(prog)s collect               # OneJAV RSS 전체 다운로드
  %(prog)s collect --dry-run     # 다운로드 미리보기
  %(prog)s collect --favorite URL  # Favorite 배우만 필터링 다운로드
        """
    )
    
    parser.add_argument(
        "command",
        choices=["classify", "collect"],
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
    
    args = parser.parse_args()
    
    # 로그 파일 위치 출력
    logger.info(f"Log file: {log_path}")
    
    # 명령 실행
    if args.command == "classify":
        from .classify import run as classify_run
        classify_run(dry_run=args.dry_run)
    
    elif args.command == "collect":
        from .collect import run as collect_run
        collect_run(dry_run=args.dry_run, max_count=args.max_downloads, favorite_url=args.favorite)


if __name__ == "__main__":
    main()
