# AI 에이전트 컨텍스트 및 가이드라인

## 1. 프로젝트 개요

이 환경은 다운로드된 토렌트 파일을 관리하고 DLNA/미디어 서버를 통해 스트리밍하기 위한 전용 시스템입니다. 이 시스템은 파일 정리를 자동화하고, 이름의 일관성을 유지하며, 스트리밍을 위한 최적의 구조를 보장합니다.

## 2. 디렉토리 구조

- **평탄화 대상 (2개):**
  - `East/`: 아시아 미디어 콘텐츠. 평탄화 대상.
  - `West/`: 서양 미디어 콘텐츠. 평탄화 대상.

- **자동 분류 대상 (14개):**
  - `Mini/`: tiny4k, exxxtrasmall, petite, tiny, pixie, small, perfectgirlfriend / CAWD-, PIYO-, MUKC-
  - `Angels/`: angelslove, angels-everywhere
  - `Dakota/`: dakota
  - `FC2/`: fc2-ppv, fc2 / FC2-PPV, FC2
  - `Kate/`: katekuray
  - `Lesbian/`: lesbian / BBAN
  - `Massage/`: massagerooms, massagesins, massage / OREMO, FSDSS
  - `Only/`: onlytarts, onlyfans
  - `POV/`: pov / ILovePOV, IntimatePOV, academypov, ilovepov
  - `Tushy/`: tushy / TUSHY
  - `Vixen/`: vixen / VIXEN
  - `WoW/`: wowgirls
  - `Cum4k/`: cum4k
  - `FTVGirls/`: ftvgirls

- **수동 관리 대상 (3개):**
  - `Minamo/`: START- 시리즈
  - `Niko/`: SONE-, SNOS- 시리즈
  - `Molester/`: NHDTC-, NHDTB- 시리즈

## 3. 자동화 스크립트

이 시스템은 단일 통합 파이썬 스크립트를 사용하여 관리를 수행합니다.

### `organize_media.py`

이 마스터 스크립트는 다음 작업들을 수행합니다:

1. **청소 (Clean):** 정크 파일(`.txt`, `.url`, `.lnk` 등) 및 스팸 영상(`sample`, `trailer`)을 삭제합니다.
2. **평탄화 (Flatten):** East, West 폴더의 하위 디렉토리에 있는 영상 파일을 루트로 이동시키고 빈 폴더를 제거합니다.
3. **이름 변경 (Rename):** 파일명에서 스팸 접두사(예: `hhd800.com@`)를 제거합니다.
4. **분류 (Sort):** SPECIAL_RULES에 따라 파일을 각 카테고리 폴더(Mini, Angels, Dakota 등)로 이동시킵니다. (상세 규칙은 섹션 2 참조)
5. **권한 설정 (Permission):** DLNA 호환성을 위해 디렉토리는 `755`, 파일은 `644`로 권한을 설정합니다.

## 4. 사용자 정의 목표

1. **파일 관리:** 분류, 중복 제거 및 청소의 자동화.
2. **스트리밍 최적화:** DLNA/Jellyfin을 위한 설정 및 권한 관리.
3. **보안:** 무시 파일(.gitignore 등) 규칙 엄수.
4. **프라이버시:** 공개 로그에 디렉토리 구조가 노출되지 않도록 주의.

## 5. 운영 표준

- **스크립트:** `organize_media.py`를 사용하며, 필요 시 리팩토링합니다.
- **안전:** "sample" 키워드와 일치하지 않는 한, 사용자 확인 없이 대용량 미디어 파일을 삭제하지 않습니다.
- **백업:** 설정 및 스크립트의 정기적인 백업을 권장합니다.
