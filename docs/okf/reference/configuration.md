---
type: reference
---

# Configuration Reference (설정 명세)

Meridian-X의 설정 파일 구조, 필수/선택 키 및 보안 관리(SOPS 암호화)에 대한 기술 명세서입니다.

---

## 1. 설정 파일 경로 및 로딩

- **기본 경로**: `config/settings.json` (보안을 위해 `.gitignore`에 등록됨)
- **템플릿 파일**: `config/settings.json.example`
- **암호화 추적본**: `config/settings.json.sops` (sops + age 암호화)
- **사용자 인증 override**: `~/.config/meridian-x/credentials.json` (선택, git 관리 밖) — 아래 [4. 사용자 인증 override](#4-사용자-인증-override-credentialsjson) 참조
- **초기화 및 재암호화 절차**: [SOPS 설정 초기화 및 암호화 가이드](../how-to/sops-configuration.md) 참조

---

## 2. settings.json 최상위 키 명세

| 최상위 키 | 필수 여부 | 설명 |
| :--- | :---: | :--- |
| `sources` | 필수 | 수집 대상 소스(OneJAV, Sukebei, XXXClub, 레거시 TorrentGalaxy) 설정 (RSS URL, 미러, 프록시 우회) |
| `collection` | 선택 | 수집 공통 옵션 (`request_timeout`, `user_agent`) 및 잔존율 기반 취향 스코어링 (`scoring.enabled`, `scoring.min_score`) |
| `transmission` | 필수 | Transmission RPC 데몬 연결 정보 (`rpc_url`, `rpc_user`, `rpc_password`, `stop_after_download`, `filters`) |
| `jellyfin` | 필수 | Jellyfin 미디어 서버 REST API 연결 정보 (`url`, `api_key`, `timeout`) |
| `remote` | 필수 | SSH 대상 원격 미디어 서버 (`host`, `user`, `path`) |
| `proxy` | 선택 | 사이트 접속 우회 HTTP 프록시 URL (gluetun). 설정 시 소스 fetch가 `proxy → lt SSH → 직접` 순서로 시도된다 |
| `flaresolverr` | 선택 | Cloudflare JS challenge 우회용 FlareSolverr (`url`: `.../v1` endpoint, `proxy`: FlareSolverr 컨테이너 기준 egress 프록시). OneJAV 전용 |
| `stashdb` | 선택 | 서양 미디어 메타데이터 조회용 StashDB GraphQL API (`api_key`) |
| `classify` | 필수 | 미디어 자동 분류 규칙 (`artists`, `artist_aliases`, `studios`, `delete_keywords`, `delete_extensions`, `clean_prefixes`) |
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
      "favorite_url": "https://onejav.com/favorite/<token>"
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
      "enabled": false,
      "base_url": "https://torrentgalaxy.one",
      "mirrors": ["https://tgx.rs", "https://torrentgalaxy.mx"],
      "category": "XXX",
      "remote": { "ssh_alias": "lt" }
    }
  }
}
```

> **TorrentGalaxy 비활성화 안내**: `torrentgalaxy.one` 및 기존 미러 도메인이 폐기·응답 불능 상태이므로 현재 기본값은 `"enabled": false`다(코드상 `/get-posts/category:{name}:format:json/` JSON API 어댑터는 보존).

> **사이트 접속 우회 및 FlareSolverr 원리**: [아키텍처 및 워크플로우 - 사이트 접속 우회](../explanation/architecture-and-workflow.md#사이트-접속-우회-egress) 참조.

> **OneJAV 즐겨찾기**: `favorite_url`은 비로그인 token 기반 즐겨찾기 페이지(사용자가 등록한 배우/tag 신작 모음)다. HTML에 `.torrent` 링크를 직접 포함하며, 수집 항목은 사용자 명시적 선택이므로 FHD 필터/dedup 없이 무조건 수집된다. `meridian favorite` 서브커맨드로 **수동 수집 전용** 동작하며 `transmission`(RSS) 수집에는 포함되지 않는다. `discover_favorite()`를 구현하는 어떤 소스든 이 경로로 추가할 수 있다. token URL은 secret이므로 `settings.json`(sops 추적본)으로만 관리한다.

```json
{
  "proxy": "http://brla.bun-bull.ts.net:8888",
  "flaresolverr": {
    "url": "http://brla.bun-bull.ts.net:8191/v1",
    "proxy": "http://gluetun:8888"
  }
}
```

### `collection` 및 `classify.artist_aliases`
```json
{
  "collection": {
    "request_timeout": 30,
    "scoring": {
      "enabled": true,
      "min_score": 10.0
    }
  },
  "classify": {
    "artists": {
      "WEST": ["Dakota Doll", "Kubera Fortuna"],
      "JPN": ["MINAMO", "Rena Miyashita", "Niko Kawagoe"]
    },
    "artist_aliases": {
      "Rena Miyashita": ["宮下玲奈"],
      "Niko Kawagoe": ["川越にこ"]
    }
  }
}
```
- `collection.scoring`: `retention_stats`(실제 디스크 잔존 스냅샷)와 메타데이터 캐시를 결합해 전 소스 후보를 글로벌 정렬하며, `min_score > 0`일 때 미만 항목을 스킵한다(`0.0`이면 정렬·로그만 수행).
- `classify.artist_aliases`: 배우 표준 폴더명(영문 `First Last`)에 한자·가나·별칭을 매핑해 분류 및 취향 스코어링 시 동일 배우로 통합한다.

### `transmission`
```json
{
  "transmission": {
    "rpc_url": "http://127.0.0.1:9091/transmission/rpc",
    "rpc_user": "media",
    "rpc_password": "YOUR_PASSWORD",
    "download_dir": null,
    "timeout": 30,
    "stop_after_download": true,
    "filters": {
      "exclude_extensions": [".html", ".url", ".txt", ".nfo"],
      "exclude_keywords": ["sample", "trailer", "preview"],
      "min_file_size_mb": 100
    }
  }
}
```

---

## 4. 사용자 인증 override (credentials.json)

API key·비밀번호 등 인증 값은 repo 밖 사용자 파일로 분리할 수 있다.

- **경로**: `$XDG_CONFIG_HOME/meridian-x/credentials.json` (기본 `~/.config/meridian-x/credentials.json`, 권장 권한 `0600`)
- **구조**: `settings.json`과 동일한 중첩 구조로 인증 필드만 기술한다
- **병합**: `load_config()`가 deep merge로 우선 적용한다. 파일이 없으면 무시되고 `settings.json`의 값이 그대로 사용된다
- **sops 불필요**: repo 밖 로컬 파일이라 git 노출 경로가 없다

```json
{
  "jellyfin": { "api_key": "..." },
  "stashdb": { "api_key": "..." },
  "transmission": { "rpc_user": "...", "rpc_password": "..." }
}
```
