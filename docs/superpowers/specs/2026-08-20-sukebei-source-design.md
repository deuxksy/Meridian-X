# Sukebei (Nyaa) Source Integration Design

- **Date**: 2026-08-20
- **Status**: Draft (Approved in Brainstorming)
- **Target**: Meridian-X (`src/meridian_x/sources/sukebei.py`)

---

## 1. Overview & Goals

Meridian-X에 성인 실사(JAV/FC2/무수정) P2P 인덱서인 **Sukebei (`sukebei.nyaa.si`)** 소스를 추가한다.
기존 `onejav` 및 `xxxclub`과 100% 호환되는 소스 표준 인터페이스를 구현하여 다음 두 가지 기능을 완벽히 지원한다:

1. **자동 수집 (`meridian transmission --source sukebei`)**: Sukebei RSS 피드(`?page=rss&c=2_2`)에서 신작을 탐색하고, 관심 배우/스튜디오 및 정규 JPN 품번 패턴과 일치하는 항목을 선별하여 Transmission에 자동 전송.
2. **키워드/품번 검색 (`meridian search <query> --source sukebei`)**: Sukebei 실시간 HTML 검색을 수행하고 시더(Seeders) 수 기준 정렬된 목록을 대화형 또는 자동(`--auto`)으로 Transmission에 전송.

---

## 2. Architecture & File Structure

### 2.1 File Layout
```text
src/
└── meridian_x/
    ├── sources/
    │   ├── __init__.py        # SOURCES 레지스트리에 sukebei 등록
    │   ├── onejav.py          # OneJAV
    │   ├── xxxclub.py         # XXXClub
    │   └── sukebei.py         # [신규] Sukebei 소스 모듈
    ├── collect.py             # Multi-source 수집 오케스트레이터
    └── cli.py                 # search 및 transmission CLI 진입점
config/
└── settings.json.example      # sukebei 기본 설정 항목 추가
tests/
└── test_sukebei.py            # [신규] Sukebei 단위 및 통합 테스트
```

### 2.2 Standard Source Interface
`sukebei.py`는 `onejav.py`, `xxxclub.py`와 동일한 4개의 핵심 표준 메서드를 구현한다:

| 함수명 | 시그니처 | 반환값 | 설명 |
| :--- | :--- | :--- | :--- |
| `discover` | `(config: dict) -> list[dict]` | `[item, ...]` | RSS 피드 수집 및 화이트리스트 필터링 |
| `resolve` | `(item: dict, config: dict) -> dict` | `{"type": "magnet", "data": "..."}` | Transmission 전송용 페이로드 생성 |
| `search` | `(query: str, category: str, config: dict) -> list[dict]` | `[item, ...]` | 웹 검색 결과 목록 반환 |
| `resolve_magnet` | `(details_url: str, config: dict) -> str \| None` | `magnet_url` | 상세 페이지 또는 캐시된 마그넷 링크 반환 |

---

## 3. Detailed Data Flow & Logic

### 3.1 Network & Bypass Strategy (`_fetch_url`)
한국 ISP의 방송통신심의위원회 Sukebei SNI 차단에 대응:
1. `config.get("remote", {}).get("ssh_alias")` (예: `"lt"`) 존재 시:
   - `ssh lt "curl -4 -sL --max-time {timeout} '{url}'"` 실행 (OneJAV와 동일한 안정적 우회)
2. `config.get("proxy")` 존재 시: `requests.get(url, proxies=...)`
3. 그 외: 로컬 `requests.get(url)`

### 3.2 RSS Discovery & Whitelist Filtering (`discover`)
- **RSS URL**: `https://sukebei.nyaa.si/?page=rss&c=2_2` (`c=2_2`: Real Life - Video)
- **RSS XML 파싱 필드**:
  - `title`: 토렌트 제목
  - `link` / `guid`: `https://sukebei.nyaa.si/view/{id}`
  - `nyaa:infoHash`: 40자리 BTIH 해시 (이 값을 이용해 `magnet:?xt=urn:btih:{infoHash}&dn={title}` 즉시 생성)
  - `nyaa:size`, `nyaa:seeders`, `nyaa:leechers`
- **화이트리스트 검사 (`is_whitelisted_title`)**:
  - `settings.json`의 `classify.artists.JPN` 관심 배우 이름 포함 여부
  - `settings.json`의 `classify.studios.JPN` 스튜디오명/별칭 포함 여부
  - 정규 품번 패턴(예: `[A-Za-z]{2,8}[-_]?\d{3,5}`, `FC2[-_ ]?PPV[-_ ]?\d+` 등) 매칭 여부

### 3.3 Payload Resolution (`resolve`)
- `item`에 `nyaa:infoHash` 또는 사전 구성된 `magnet_url`이 포함되어 있으므로 추가 HTTP 네트워크 요청 없이 `{"type": "magnet", "data": magnet_url}`을 $O(1)$로 즉시 반환.

### 3.4 Keyword & ID Search (`search`)
- **Search URL**: `https://sukebei.nyaa.si/?f=0&c=2_2&q={encoded_query}&s=seeders&o=desc`
- **HTML DOM 파싱 (`table.torrent-list tbody tr`)**:
  - `td:nth-of-type(2) a:not(.comments)`: 제목 및 상세 페이지 URL (`/view/{id}`)
  - `td:nth-of-type(3) a[href^="magnet:"]`: 마그넷 링크
  - `td:nth-of-type(4)`: 파일 크기
  - `td:nth-of-type(6)`: Seeders 수
  - `td:nth-of-type(7)`: Leechers 수
- **`resolve_magnet`**: 검색 아이템에 이미 `magnet:`이 포함되어 있으면 그대로 반환하고, 상세 URL만 있을 경우 상세 페이지에서 `a[href^="magnet:"]` 추출.

---

## 4. Configuration Specification

`config/settings.json.example`에 추가될 기본 설정:
```json
{
  "sources": {
    "sukebei": {
      "enabled": true,
      "base_url": "https://sukebei.nyaa.si",
      "rss_url": "https://sukebei.nyaa.si/?page=rss&c=2_2",
      "default_category": "2_2",
      "request_timeout": 30,
      "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
  }
}
```

---

## 5. Verification & Testing Strategy

1. **`tests/test_sukebei.py` 작성**:
   - `test_sukebei_rss_parsing_and_filtering`: Mock RSS XML을 이용한 아이템 파싱 및 관심 배우/스튜디오 필터링 검증
   - `test_sukebei_resolve_magnet`: infoHash로부터 마그넷 URL 생성 검증
   - `test_sukebei_html_search_parsing`: Mock Search HTML로부터 테이블 파싱, 마그넷 링크, 시더 수 추출 검증
   - `test_sukebei_cli_integration`: `meridian search <query> --source sukebei` 명령의 Transmission 및 DB 기록 mock 검증
2. **전체 회귀 테스트**:
   - `uv run pytest tests/ -v`를 수행하여 모든 기존 111+ 개 테스트 통과 확인.
