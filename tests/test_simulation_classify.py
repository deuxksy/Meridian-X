#!/usr/bin/env python3
"""시뮬레이션 기반 classify 로직 테스트 스크립트"""
import logging
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가 (Python 모듈 임포트 문제 해결)
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.meridian_x.classify import run as classify_run

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # WowGirls/Wowgirls 중복 폴더 파일 목록 시뮬레이션 데이터
    simulation_files = [
        "WowGirls/wowgirls.18.08.31.shrima.malati.stefanie.moon.and.elle.rose.incredible.foursome.mp4",
        "WowGirls/wowgirls.18.09.14.cayla.and.alexa.tomas.beautiful.daybreak.mp4",
        "Wowgirls/wowgirls.23.05.02.alissa.foxy.kinky.moods.mp4",
        "Wowgirls/wowgirls.23.05.06.evelin.elle.gorgeous.date.mp4"
    ]

    logger.info("=== 시뮬레이션 기반 classify 로직 테스트 시작 ===")
    logger.info(f"시뮬레이션 파일 수: {len(simulation_files)}개")

    # classify_run 호출 (dry-run 모드, 시뮬레이션 데이터 전달)
    classify_run(
        dry_run=True,
        refresh=False,
        simulation_files=simulation_files
    )

    logger.info("=== 시뮬레이션 테스트 완료 ===")