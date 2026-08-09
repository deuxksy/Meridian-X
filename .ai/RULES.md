# Meridian-X Common Agent Rules (Single Source of Truth)

미디어 컬렉션 자동화 큐레이션 및 URL 직링크 추출/aria2 전송 스위트.

## Commands

```bash
# Setup
uv sync
cp config/settings.json.example config/settings.json

# Meridian Pipeline Commands
uv run meridian pipeline --dry-run
uv run meridian pipeline

# URL Resolver Commands (Shortener Bypass & Direct Link Extraction)
uv run url-resolver parse "https://misskon.com/114764-..."
uv run url-resolver crawl "https://misskon.com/tag/you-shui-ling-yi/" --pages 0
uv run url-resolver crawl "https://cosplaytele.com/category/byoru/" --pages 2 --extract-only

# Tests
uv run pytest tests/ -v
```

## Architecture

```text
src/
├── meridian_x/       # RSS 수집, Transmission, Jellyfin 큐레이션 및 정제
└── url_resolver/     # [NEW] misskon/cosplaytele 파싱, ouo.io 바이패스 & aria2 전송 CLI
    ├── cli.py        # url-resolver CLI 진입점 (parse, crawl, clip, batch)
    ├── models.py     # DownloadMetadata (direct_url, referer, tags, models)
    ├── config.py     # config.toml 설정 로더
    ├── extractors/   # misskon, cosplaytele, mediafire, ouo (Playwright) 파서
    └── dispatchers/  # aria2p RPC 디스패처
```
