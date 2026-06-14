"""
Meridian-X Collect Module
Multi-source RSS 수집 → Transmission RPC 전송
"""
import logging

from .core import load_config, load_downloaded_history, save_downloaded_history
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
        timeout=transmission_config.get("timeout", 10),
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

    # history 로드
    history = load_downloaded_history(history_file)

    remaining = max_count
    total_count = 0

    for src_name, src_config in active_sources.items():
        if remaining <= 0:
            break

        src_module = SOURCES[src_name]
        logger.info(f"\n--- Source: {src_name} ---")

        # 공통 설정과 source 설정 병합 (Codex 검증 반영)
        effective_config = {**collection_config, **src_config, "remote": config.get("remote", {})}

        try:
            # discover
            items = src_module.discover(effective_config)
            logger.info(f"Found {len(items)} items")

            if not items:
                logger.info("No items found")
                continue

            # history 필터링
            new_items = [i for i in items if i["id"] not in history]
            src_history_count = len([h for h in history if h.startswith(src_name + ":")])
            logger.info(f"New: {len(new_items)} (History: {src_history_count})")

            if not new_items:
                continue

            # 전체 max_count 내에서 제한
            to_process = new_items[:remaining]
            logger.info(f"Will process {len(to_process)} items")

            count = 0
            for item in to_process:
                item_id = item["id"]

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
                        history.add(item_id)
                        count += 1
                    else:
                        logger.warning(f"  [Failed] {item_id}")
                except Exception as e:
                    logger.error(f"  [RPC Error] {item_id}: {e}")

            remaining -= count
            total_count += count
            logger.info(f"Source {src_name}: {count} sent")

        except Exception as e:
            # per-source exception boundary (Codex 검증 반영)
            logger.error(f"Source {src_name} failed: {e}")
            continue

    # history 저장
    save_downloaded_history(history_file, history)
    logger.info(f"=== Meridian-X Collect Completed ({total_count} total) ===")
