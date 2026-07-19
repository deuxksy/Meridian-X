#!/usr/bin/env python3
"""onejav gate probe — Playwright fingerprint 통과 검증.

기존 방식(SSH command exec + curl) 대신 Playwright pivot:
heritage 를 SOCKS5 exit 로 사용 + 브라우저 fingerprint 로 onejav RSS gate 통과 검증.

PASS = onejav RSS 게이트가 200 + <rss> 반환. 4 launch variant 순회, 첫 PASS 에서 break.

실행: uv run python scripts/probe_onejav_gate.py
종료코드: 0=PASS(최소 1 variant 통과), 1=FAIL(전 variant 실패)
"""
import os
import sys
import json
import time
import socket
import subprocess
from pathlib import Path

CFG_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.json"
GATE_URL_DEFAULT = "https://onejav.com/feeds/"
UA_DEFAULT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"

# gate 통과 검증용 4 launch variant. 전원 동일 SOCKS proxy + onejav URL.
VARIANTS = [
    ("bundled-headless", {"headless": True}),
    ("disable-blink", {"headless": True, "args": ["--disable-blink-features=AutomationControlled"]}),
    ("chrome-channel", {"channel": "chrome"}),
    ("bundled-headed", {"headless": False}),
]


def load_config():
    with open(CFG_PATH) as f:
        return json.load(f)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def resolve_key(cfg_key):
    # 핸드오프 expanduser 수정 + 이 Mac(axiom) 폴백.
    # config ssh_key 는 crong NixOS 경로(/opt/data/home/...)일 수 있음 → 없으면 ~/.ssh/id_ed25519.
    key = os.path.expanduser(cfg_key) if cfg_key else ""
    if key and os.path.exists(key):
        return key
    fallback = os.path.expanduser("~/.ssh/id_ed25519")
    if os.path.exists(fallback):
        print(f"[key] cfg key 미존재({cfg_key}) → 폴백 {fallback}")
        return fallback
    raise FileNotFoundError(f"SSH key not found: cfg={cfg_key}, fallback={fallback}")


def open_tunnel(host, user, key, port):
    # -fN: 백그라운드 daemonize. ExitOnForwardFailure: 포트 바인딩 실패 시 즉시 종료.
    cmd = [
        "ssh", "-fN",
        "-D", f"127.0.0.1:{port}",
        "-i", key,
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "ConnectTimeout=8",
        "-o", "ServerAliveInterval=30",
        f"{user}@{host}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    if proc.returncode != 0:
        raise RuntimeError(f"ssh tunnel failed rc={proc.returncode}: {proc.stderr.strip()[:300]}")


def close_tunnel(port):
    # port 는 동적 할당(고유) → 해당 포트만 종료, 다른 tunnel 영향無.
    subprocess.run(["pkill", "-f", f"-D.*127.0.0.1:{port}"], capture_output=True)


def main():
    cfg = load_config()
    remote = cfg.get("remote", {})
    host = remote.get("host", "100.96.115.19")
    user = remote.get("user", "media")
    key = resolve_key(remote.get("ssh_key"))
    gate = cfg.get("sources", {}).get("onejav", {}).get("rss_url", GATE_URL_DEFAULT)
    ua = cfg.get("collection", {}).get("user_agent", UA_DEFAULT)

    port = free_port()
    print(f"[tunnel] SOCKS5 127.0.0.1:{port} via {user}@{host} (key={key})")
    open_tunnel(host, user, key, port)
    time.sleep(1.5)
    print(f"[gate] {gate}")

    from playwright.sync_api import sync_playwright
    proxy = {"server": f"socks5://127.0.0.1:{port}"}
    results = []
    winner = None
    try:
        with sync_playwright() as p:
            for name, opts in VARIANTS:
                print(f"\n=== {name} ===")
                try:
                    browser = p.chromium.launch(proxy=proxy, **opts)
                except Exception as e:
                    print(f"  LAUNCH FAIL {type(e).__name__}: {str(e)[:200]}")
                    results.append((name, False, f"launch:{type(e).__name__}"))
                    continue
                try:
                    ctx = browser.new_context(user_agent=ua)
                    page = ctx.new_page()
                    resp = page.goto(gate, timeout=30000, wait_until="domcontentloaded")
                    status = resp.status if resp else 0
                    body = page.content()
                    has_rss = "<rss" in body.lower()
                    ok = status == 200 and has_rss
                    print(f"  status={status} rss={has_rss} ok={ok}")
                    print(f"  body[:140]={body[:140].replace(chr(10), ' ')}")
                    results.append((name, ok, f"status={status}"))
                    if ok:
                        winner = name
                        break
                except Exception as e:
                    print(f"  NAV FAIL {type(e).__name__}: {str(e)[:200]}")
                    results.append((name, False, f"nav:{type(e).__name__}"))
                finally:
                    browser.close()
    finally:
        close_tunnel(port)
        print(f"\n[tunnel] closed port {port}")

    print("\n=== MATRIX ===")
    for name, ok, detail in results:
        print(f"  {name:20} {'PASS' if ok else 'FAIL'}  ({detail})")
    print(f"\nGATE {'PASSED' if winner else 'FAILED'}" + (f" via {winner}" if winner else ""))
    sys.exit(0 if winner else 1)


if __name__ == "__main__":
    main()
