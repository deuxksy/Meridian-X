# AGENTS.md

Codex/AGENTS.md 전용 instruction이다.

이 저장소의 공통 프로젝트 instruction은 root `.ai/RULES.md`가 Single Source of Truth다. 작업 전 반드시 `.ai/RULES.md`를 읽고 Commands, Architecture, Key Patterns, Verification, Gotchas를 따른다.

Codex의 AGENTS.md reference는 native import가 아니라 instruction-based best-effort다. Claude 전용 세부 운영 맥락이 필요할 때만 `CLAUDE.md`를 참고한다.

## Codex Specific Instructions

- `codex exec` 등 비대화형 실행에서는 승인 프롬프트에 의존하지 않는다. transmission, tidy, classify, pipeline 등 원격·외부 변경은 `--dry-run` 결과를 먼저 출력하고 실제 실행은 사용자 명령을 기다린다.
- 리뷰 모드(`codex exec review`)로 호출된 경우에는 변경 diff만 평가하고 파일을 수정하지 않는다.
