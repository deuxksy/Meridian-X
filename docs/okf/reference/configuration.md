# Configuration Reference (설정 명세)

Meridian-X의 설정 파일 구조, 필수/선택 키 및 보안 관리(SOPS 암호화)에 대한 기술 명세서입니다.

---

## 1. 설정 파일 경로 및 로딩

- **기본 경로**: `config/settings.json` (보안을 위해 `.gitignore`에 등록됨)
- **템플릿 파일**: `config/settings.json.example`
- **암호화 추적본**: `config/settings.json.sops` (sops + age 암호화)

### 설정 초기화 방법
```bash
# 템플릿 복사 후 직접 편집
cp config/settings.json.example config/settings.json

# 또는 sops로 암호화된 설정 복원
sops --decrypt --input-type binary --output-type binary config/settings.json.sops > config/settings.json
```

---

## 2. settings.json 최상위 키 명세

| 최상위 키 | 필수 여부 | 설명 |
| :--- | :---: | :--- |
| `sources` | 필수 | 수집 대상 소스(OneJAV, Sukebei, XXXClub, TorrentGalaxy) 설정 (RSS URL, 미러, 프록시 우회) |
| `transmission` | 필수 | Transmission RPC 데몬 연결 정보 (`rpc_url`, `rpc_user`, `rpc_password`, `stop_after_download`, `filters`) |
| `jellyfin` | 필수 | Jellyfin 미디어 서버 REST API 연결 정보 (`url`, `api_key`, `timeout`) |
| `remote` | 필수 | SSH 대상 원격 미디어 서버 (`host`, `user`, `path`) |
| `fanza` | 선택 | 공식 JAV 메타데이터 조회용 FANZA API (`api_id`, `affiliate_id`) |
| `stashdb` | 선택 | 서양 미디어 메타데이터 조회용 StashDB GraphQL API (`api_key`) |
| `classify` | 필수 | 미디어 자동 분류 규칙 (`artists`, `studios`, `delete_keywords`, `delete_extensions`, `clean_prefixes`) |
| `genres` | 선택 | 장르별 키워드 및 접두사 매핑 규칙 |

---

## 3. 세부 설정 스키마

### `sources`
```json
{
  "sources": {
    "onejav": {
      "enabled": true,
      "base_url": "https://onejav.com",
      "rss_url": "https://onejav.com/feeds/",
      "remote": { "ssh_alias": "lt" }
    },
    "sukebei": {
      "enabled": true,
      "base_url": "https://sukebei.nyaa.si",
      "rss_url": "https://sukebei.nyaa.si/?page=rss&c=2_2",
      "default_category": "2_2",
      "remote": { "ssh_alias": "lt" }
    },
    "xxxclub": {
      "enabled": true,
      "rss_url": "https://xxxclub.to/feed/1080p.FullHD.xml",
      "selective_only": true
    },
    "torrentgalaxy": {
      "enabled": true,
      "base_url": "https://torrentgalaxy.to",
      "mirrors": ["https://torrentgalaxy.one", "https://tgx.rs"],
      "rss_url": "https://torrentgalaxy.to/rss?cat=42",
      "default_category": "42",
      "remote": { "ssh_alias": "lt" }
    }
  }
}
```

### `transmission`
```json
{
  "transmission": {
    "rpc_url": "http://127.0.0.1:9091/transmission/rpc",
    "rpc_user": "media",
    "rpc_password": "YOUR_PASSWORD",
    "download_dir": null,
    "timeout": 10,
    "stop_after_download": true,
    "filters": {
      "exclude_extensions": [".html", ".url", ".txt", ".nfo"],
      "exclude_keywords": ["sample", "trailer", "preview"],
      "min_file_size_mb": 100
    }
  }
}
```
