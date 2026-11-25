# Meridian-X Claude Instructions

@./.ai/RULES.md

이 파일은 Claude 전용 보조 instruction이다. 공통 프로젝트 규칙, command, architecture, verification, gotcha는 `.ai/RULES.md`를 Single Source of Truth로 따른다.

## Claude-specific workflow

- `claude -p` 실행은 `.ai/RULES.md` Verification의 비대화형(headless) `--dry-run` 선행 규칙을 따른다.
- 서브에이전트 위임 시에도 `.ai/RULES.md`의 SOPS/원격 SSH(`media` 계정) 제약을 프롬프트에 명시해 전달한다.
