# Meridian-X Claude Instructions

@./.ai/RULES.md

이 파일은 Claude 전용 보조 instruction이다. 공통 프로젝트 규칙, command, architecture, verification, gotcha는 `.ai/RULES.md`를 Single Source of Truth로 따른다.

## Claude-specific workflow

- 비대화형(`claude -p`) 실행 시에는 승인 프롬프트에 의존하지 않고, transmission, favorite, tidy, classify, pipeline 등 원격·외부 변경은 `--dry-run` 결과를 먼저 제시한 뒤 사용자 명령을 기다린다.
- 서브에이전트 위임 시에도 `.ai/RULES.md`의 SOPS/원격 SSH(`media` 계정) 제약을 프롬프트에 명시해 전달한다.
