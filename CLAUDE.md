# Meridian-X Claude Instructions

@./.ai/RULES.md

이 파일은 Claude 전용 보조 instruction이다. 공통 프로젝트 규칙, command, architecture, verification, gotcha는 `.ai/RULES.md`를 Single Source of Truth로 따른다.

## Claude-specific workflow

- 구현 전 변경 범위를 먼저 좁히고, 가능한 한 작은 diff로 작업한다.
- 원격 파일 이동, Transmission/Jellyfin 조작, 외부 API 조회는 dry-run 또는 읽기 전용 확인을 먼저 수행한다.
- 새로운 CLI 기능 또는 동작 변경은 관련 단위 테스트를 먼저 추가/수정한 뒤 구현한다.
- Secret, API key, token, DB 연결 정보는 평문으로 작성하지 않는다. 설정 복원/암호화는 `.ai/RULES.md`의 sops 흐름을 따른다.

## Project notes

- pipeline 마지막 단계의 `report`는 디스크 사용량과 Transmission 토렌트 상태를 출력한다.
- 웹 화보 및 단축링크 우회/직링크 추출은 독립 자매 프로젝트 `Vesper-X`로 분리 관리한다.
- README와 문서 구조는 `docs/README.md`의 Diátaxis 인덱스를 기준으로 유지한다.
