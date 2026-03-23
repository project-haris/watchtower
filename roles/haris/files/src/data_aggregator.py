#!/usr/bin/env python3
"""Poll local Signal K state and forward JSON snapshots to the SOC."""

import json
import logging
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_API_URL = "http://127.0.0.1:3000/signalk/v1/api/vessels/self"
DEFAULT_LOG_PATH = "/opt/haris/logs/signalk_snapshots.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_signalk_snapshot(api_url: str) -> dict:
    with urlopen(api_url, timeout=10) as response:
        return json.load(response)


def api_root_url(api_url: str) -> str:
    marker = "/vessels/self"
    if api_url.endswith(marker):
        return api_url[: -len(marker)] + "/"
    return api_url


def fetch_signalk_snapshot_with_fallback(api_url: str) -> dict:
    fallback_exc = None
    try:
        return fetch_signalk_snapshot(api_url)
    except HTTPError as exc:
        if exc.code != 404:
            raise
        fallback_exc = exc

    root_url = api_root_url(api_url)
    if root_url == api_url:
        raise fallback_exc

    logger.warning(
        "Signal K endpoint %s returned 404; falling back to API root %s",
        api_url,
        root_url,
    )
    return fetch_signalk_snapshot(root_url)


def build_event(payload: dict) -> dict:
    return {
        "@timestamp": utc_now(),
        "source": "haris_signalk",
        "haris_host": socket.gethostname(),
        "vessel_id": os.getenv("HARIS_VESSEL_ID", "UNKNOWN"),
        "vessel_name": os.getenv("HARIS_VESSEL_NAME", "UNKNOWN"),
        "signalk": payload,
    }


def write_jsonl(log_path: str, event: dict) -> None:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, separators=(",", ":")))
        handle.write("\n")


def forward_event(host: str, port: int, event: dict) -> None:
    message = json.dumps(event, separators=(",", ":")) + "\n"
    with socket.create_connection((host, port), timeout=10) as conn:
        conn.sendall(message.encode("utf-8"))


def main() -> None:
    api_url = os.getenv("HARIS_SIGNALK_API_URL", DEFAULT_API_URL)
    snapshot_interval = float(os.getenv("HARIS_SNAPSHOT_INTERVAL", "10"))
    log_path = os.getenv("HARIS_LOG_PATH", DEFAULT_LOG_PATH)
    forward_enabled = os.getenv("HARIS_SOC_FORWARD_ENABLED", "false").lower() == "true"
    soc_host = os.getenv("HARIS_SOC_LOG_HOST", "")
    soc_port = int(os.getenv("HARIS_SOC_LOG_PORT", "5045"))

    logger.info("Starting Haris Signal K forwarder")
    logger.info("Signal K API: %s", api_url)
    logger.info("Local JSONL log: %s", log_path)
    if forward_enabled:
        logger.info("SOC forwarding enabled to %s:%s", soc_host, soc_port)
    else:
        logger.info("SOC forwarding disabled")

    while True:
        try:
            payload = fetch_signalk_snapshot_with_fallback(api_url)
            event = build_event(payload)
            write_jsonl(log_path, event)

            if forward_enabled and soc_host:
                forward_event(soc_host, soc_port, event)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            logger.error("Signal K forwarding cycle failed: %s", exc)

        time.sleep(snapshot_interval)


if __name__ == "__main__":
    main()
