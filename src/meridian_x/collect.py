"""
Meridian-X Collect Module
Multi-source RSS 수집 → Transmission RPC 전송
"""
import logging
from pathlib import Path

from .core import load_config, lookup_cached_metadata, score_taste
from .db import MeridianDB
from .sources import SOURCES
from .transmission import TransmissionClient

logger = logging.getLogger(__name__)


def run_transmission(max_count: int = 30, source: str = None, dry_run: bool = False) -> None:
    """Multi-source RSS 수집 → Transmission RPC 전송."""
    config = load_config()
    sources_config = config.get("sources", {})
    transmission_config = config.get("transmission", {})
    collection_config = config.get("collection", config.get("download", {}))

    if not transmission_config.get("rpc_url"):
        logger.error("transmission.rpc_url not configured")
        return

    # Transmission 클라이언트
    client = TransmissionClient(
        rpc_url=transmission_config["rpc_url"],
        user=transmission_config.get("rpc_user"),
        password=transmission_config.get("rpc_password"),
        timeout=transmission_config.get("timeout", 30),
        stop_after_download=transmission_config.get("stop_after_download", False)
    )
    filters = transmission_config.get("filters", {})
    download_dir = transmission_config.get("download_dir")
    history_file = collection_config.get("history_file", "logs/downloads.txt")

    # 활성 source 결정
    active_sources = {}
    for name, src_config in sources_config.items():
        if not src_config.get("enabled", True):
            continue
        if source and name != source:
            continue
        if name not in SOURCES:
            logger.warning(f"Unknown source: {name}")
            continue
        active_sources[name] = src_config

    if not active_sources:
        logger.error("No active sources")
        return

    logger.info("=== Meridian-X Collect Started ===")
    logger.info(f"Sources: {list(active_sources.keys())}")

    # history 로드 (MeridianDB 사용)
    db = MeridianDB()
    if history_file and Path(history_file).exists():
        db.migrate_history_txt(history_file)
    history = db.get_download_history()
    retention_stats = db.get_retention_stats()
    raw_jav_cache = db.get_all_jav_metadata() if hasattr(db, "get_all_jav_metadata") else {}
    raw_west_cache = db.get_all_west_metadata() if hasattr(db, "get_all_west_metadata") else {}
    jav_cache = raw_jav_cache if isinstance(raw_jav_cache, dict) else {}
    west_cache = raw_west_cache if isinstance(raw_west_cache, dict) else {}

    scoring_cfg = collection_config.get("scoring", {})
    scoring_enabled = scoring_cfg.get("enabled", True) if isinstance(scoring_cfg, dict) else True
    min_score = float(scoring_cfg.get("min_score", 0.0)) if isinstance(scoring_cfg, dict) else 0.0

    # Phase 1: 전 소스 discover 및 신규 항목 수집 (per-source exception boundary 유지)
    candidates: list[tuple[str, object, dict, dict]] = []
    for src_name, src_config in active_sources.items():
        src_module = SOURCES[src_name]
        logger.info(f"\n--- Source: {src_name} ---")

        effective_config = {
            **collection_config,
            "proxy": config.get("proxy"),
            "proxies": config.get("proxies"),
            "flaresolverr": config.get("flaresolverr"),
            **src_config,
            "remote": config.get("remote", {}),
            "classify": config.get("classify", {}),
            "genres": config.get("genres", {}),
        }

        try:
            items = src_module.discover(effective_config)
            logger.info(f"Found {len(items)} items")
            new_items = [i for i in items if i["id"] not in history]
            src_history_count = len([h for h in history if h.startswith(src_name + ":")])
            logger.info(f"New: {len(new_items)} (History: {src_history_count})")
            for item in new_items:
                candidates.append((src_name, src_module, effective_config, item))
        except Exception as e:
            # per-source exception boundary (Codex 검증 반영)
            logger.error(f"Source {src_name} failed: {e}")
            continue

    # Phase 2: 전 소스 글로벌 스코어링, 안정 정렬 및 선택적 컷오프
    scored_map: dict[str, tuple[float, list[str]]] = {}
    if scoring_enabled and candidates:
        for _src_name, _src_module, eff_cfg, item in candidates:
            cached_meta = lookup_cached_metadata(item, jav_cache, west_cache)
            scored_map[item["id"]] = score_taste(item, eff_cfg, retention_stats, metadata=cached_meta)
        candidates = sorted(candidates, key=lambda c: scored_map[c[3]["id"]][0], reverse=True)
        if min_score > 0:
            before = len(candidates)
            candidates = [c for c in candidates if scored_map[c[3]["id"]][0] >= min_score]
            skipped = before - len(candidates)
            if skipped:
                logger.info(f"[Scoring] Skipped {skipped} items globally below min_score={min_score:.1f}")

    to_process = candidates[:max_count]
    logger.info(f"\n=== Global Queue: {len(to_process)} / {len(candidates)} candidates (max={max_count}) ===")

    # Phase 3: 선택된 상위 항목 resolve 및 Transmission 전송
    total_count = 0
    per_source_sent: dict[str, int] = {}
    for src_name, src_module, eff_cfg, item in to_process:
        item_id = item["id"]
        if item_id in scored_map:
            sc, reasons = scored_map[item_id]
            reason_str = ", ".join(reasons) if reasons else "unmatched"
            logger.info(f"  [Score {sc:.1f}] [{src_name}] {item_id} ({reason_str})")

        if dry_run:
            logger.info(f"  [Dry-run] {item_id}: {item.get('title', '')}")
            total_count += 1
            per_source_sent[src_name] = per_source_sent.get(src_name, 0) + 1
            continue

        try:
            payload = src_module.resolve(item, eff_cfg)
        except Exception as e:
            logger.error(f"  [Resolve Error] {item_id}: {e}")
            continue

        if not payload:
            logger.warning(f"  [Skip] {item_id} - resolve returned None")
            continue

        try:
            if payload["type"] == "metainfo":
                ok = client.add_torrent(payload["data"], download_dir=download_dir, filters=filters)
            elif payload["type"] == "magnet":
                ok = client.add_magnet(payload["data"], download_dir=download_dir, filters=filters)
            else:
                logger.warning(f"  [Skip] {item_id} - unknown payload type: {payload['type']}")
                continue

            if ok:
                logger.info(f"  [Sent] {item_id}")
                db.add_download_history([item_id])
                history.add(item_id)
                total_count += 1
                per_source_sent[src_name] = per_source_sent.get(src_name, 0) + 1
            else:
                logger.error(f"  [Failed] {item_id}")
        except Exception as e:
            logger.error(f"  [Transmission Error] {item_id}: {e}")

    for src_name, cnt in per_source_sent.items():
        logger.info(f"Source {src_name}: {cnt} sent")

    logger.info(f"=== Meridian-X Collect Completed ({total_count} total) ===")


def _filter_and_send(
    src_module,
    src_name: str,
    effective_config: dict,
    items: list,
    client,
    db,
    history: set,
    filters: dict,
    download_dir,
    remaining: int,
    dry_run: bool,
    retention_stats: dict | None = None,
) -> int:
    """history 필터링 → 취향 스코어 정렬/선택적 컷오프 → resolve → Transmission 전송. 전송 성공 수 반환."""
    if not items:
        logger.info("No items found")
        return 0

    new_items = [i for i in items if i["id"] not in history]
    src_history_count = len([h for h in history if h.startswith(src_name + ":")])
    logger.info(f"New: {len(new_items)} (History: {src_history_count})")

    if not new_items:
        return 0

    scoring_cfg = effective_config.get("scoring", {})
    scoring_enabled = scoring_cfg.get("enabled", True) if isinstance(scoring_cfg, dict) else True
    min_score = float(scoring_cfg.get("min_score", 0.0)) if isinstance(scoring_cfg, dict) else 0.0

    scored_map: dict[str, tuple[float, list[str]]] = {}
    if scoring_enabled:
        for item in new_items:
            scored_map[item["id"]] = score_taste(item, effective_config, retention_stats)
        new_items = sorted(new_items, key=lambda i: scored_map[i["id"]][0], reverse=True)
        if min_score > 0:
            before = len(new_items)
            new_items = [i for i in new_items if scored_map[i["id"]][0] >= min_score]
            skipped = before - len(new_items)
            if skipped:
                logger.info(f"  [Scoring] Skipped {skipped} items below min_score={min_score:.1f}")

    to_process = new_items[:remaining]
    logger.info(f"Will process {len(to_process)} items")

    count = 0
    for item in to_process:
        item_id = item["id"]
        if item_id in scored_map:
            sc, reasons = scored_map[item_id]
            reason_str = ", ".join(reasons) if reasons else "unmatched"
            logger.info(f"  [Score {sc:.1f}] {item_id} ({reason_str})")

        if dry_run:
            logger.info(f"  [Dry-run] {item_id}: {item.get('title', '')}")
            count += 1
            continue

        # resolve
        try:
            payload = src_module.resolve(item, effective_config)
        except Exception as e:
            logger.error(f"  [Resolve Error] {item_id}: {e}")
            continue

        if not payload:
            logger.warning(f"  [Skip] {item_id} - resolve returned None")
            continue

        # 전송
        try:
            if payload["type"] == "metainfo":
                ok = client.add_torrent(payload["data"], download_dir=download_dir, filters=filters)
            elif payload["type"] == "magnet":
                ok = client.add_magnet(payload["data"], download_dir=download_dir, filters=filters)
            else:
                logger.warning(f"  [Skip] {item_id} - unknown payload type: {payload['type']}")
                continue

            if ok:
                logger.info(f"  [Sent] {item_id}")
                db.add_download_history([item_id])
                history.add(item_id)
                count += 1
            else:
                logger.warning(f"  [Failed] {item_id}")
        except Exception as e:
            logger.error(f"  [RPC Error] {item_id}: {e}")

    return count


def run_favorite(dry_run: bool = False) -> None:
    """즐겨찾기 수집 (meridian favorite) — discover_favorite 보유 + favorite_url 설정 소스만."""
    config = load_config()
    sources_config = config.get("sources", {})
    transmission_config = config.get("transmission", {})
    collection_config = config.get("collection", config.get("download", {}))

    if not transmission_config.get("rpc_url"):
        logger.error("transmission.rpc_url not configured")
        return

    client = TransmissionClient(
        rpc_url=transmission_config["rpc_url"],
        user=transmission_config.get("rpc_user"),
        password=transmission_config.get("rpc_password"),
        timeout=transmission_config.get("timeout", 30),
        stop_after_download=transmission_config.get("stop_after_download", False)
    )
    filters = transmission_config.get("filters", {})
    download_dir = transmission_config.get("download_dir")

    active = {
        name: src_config
        for name, src_config in sources_config.items()
        if src_config.get("enabled", True)
        and src_config.get("favorite_url")
        and name in SOURCES
        and hasattr(SOURCES[name], "discover_favorite")
    }
    if not active:
        logger.info("=== Favorite Collect: favorite_url이 설정된 소스 없음 ===")
        return

    logger.info(f"=== Favorite Collect Started: {list(active.keys())} ===")
    db = MeridianDB()
    history = db.get_download_history()

    total_count = 0
    for src_name, src_config in active.items():
        src_module = SOURCES[src_name]
        logger.info(f"\n--- Source: {src_name} (favorite) ---")

        effective_config = {
            **collection_config,
            "proxy": config.get("proxy"),
            "proxies": config.get("proxies"),
            "flaresolverr": config.get("flaresolverr"),
            **src_config,
            "remote": config.get("remote", {}),
            "classify": config.get("classify", {}),
            "genres": config.get("genres", {}),
        }

        try:
            items = src_module.discover_favorite(effective_config)
            logger.info(f"Found {len(items)} favorite items")

            count = _filter_and_send(
                src_module, src_name, effective_config, items,
                client, db, history, filters, download_dir,
                remaining=len(items), dry_run=dry_run,
            )
            total_count += count
            logger.info(f"Source {src_name} (favorite): {count} sent")
        except Exception as e:
            logger.error(f"Source {src_name} favorite collect failed: {e}")
            continue

    logger.info(f"=== Favorite Collect Completed ({total_count} total) ===")
