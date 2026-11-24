---
type: how-to
---

# SOPS 설정 초기화 및 암호화 가이드

설정의 전체 키 스키마는 [Configuration Reference](../reference/configuration.md) 참조.

## 설정 초기화 방법
```bash
# 템플릿 복사 후 직접 편집
cp config/settings.json.example config/settings.json

# 또는 sops로 암호화된 설정 복원
sops --decrypt --input-type binary --output-type binary config/settings.json.sops > config/settings.json

# settings.json 편집 후 암호화 추적본 갱신
sops --encrypt --input-type binary --output-type binary config/settings.json > config/settings.json.sops
```
