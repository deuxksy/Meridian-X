#!/usr/bin/env python3
"""onejav ECH(Encrypted Client Hello) probe — SNI 기반 차단 우회 가능성 검증.

기존 probe(probe_onejav_gate.py)는 4 variant 전부 TLS Client Hello 직후 RST 확인.
원인 = SNI(onejav.com 평문) 노출 후 DPI/차단. ECH 로 SNI 암호화 시 통과 가능성 테스트.

tunnel 없이 이 Mac 직접 + DoH(Cloudflare) 로 HTTPS RR(ECH key 포함) 획득 → ECH 사용.

PASS = ECH 로 SNI 암호화 후 200 + <rss>. 차단 주체가 ISP/DPI 면 우회, Cloudflare 자체 block 이면 동일 RST.

실행: uv run python scripts/probe_onejav_ech.py
종료코드: 0=PASS(ECH 우회 성공), 1=FAIL(ECH 로도 RST)
"""
import sys
import json
from pathlib import Path

CFG_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.json"
GATE_URL_DEFAULT = "https://onejav.com/feeds/"
UA_DEFAULT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"

# ECH 활성화 + DoH(Cloudflare) 강제. DoH 로 HTTPS RR(ECH key) 획득해야 ECH 동작.
ECH_ARGS = [
    "--enable-features=EncryptedClientHello",
    "--dns-over-https-mode=secure",
    "--dns-over-https-templates=https://cloudflare-dns.com/dns-query",
]


def load_config():
    with open(CFG_PATH) as f:
        return json.load(f)


def main():
    cfg = load_config()
    gate = cfg.get("sources", {}).get("onejav", {}).get("rss_url", GATE_URL_DEFAULT)
    ua = cfg.get("collection", {}).get("user_agent", UA_DEFAULT)
    print(f"[ech] {gate} (direct, no tunnel, DoH=cloudflare)")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=ECH_ARGS)  # proxy=None (직접)
        try:
            ctx = browser.new_context(user_agent=ua)
            page = ctx.new_page()
            try:
                resp = page.goto(gate, timeout=30000, wait_until="domcontentloaded")
                status = resp.status if resp else 0
                body = page.content()
                has_rss = "<rss" in body.lower()
                ok = status == 200 and has_rss
                print(f"  status={status} rss={has_rss} ok={ok}")
                print(f"  body[:140]={body[:140].replace(chr(10), ' ')}")
                print(f"\nECH {'PASSED' if ok else 'FAILED'}")
                sys.exit(0 if ok else 1)
            except Exception as e:
                print(f"  NAV FAIL {type(e).__name__}: {str(e)[:200]}")
                print("\nECH FAILED (RST 지속 → 차단 주체가 Cloudflare 자체 block 또는 ECH 미우회)")
                sys.exit(1)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
