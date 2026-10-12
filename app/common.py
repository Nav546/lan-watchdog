"""Shared helpers: append security events to a JSONL log and send rate-limited alerts."""
import json
import os
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(os.environ.get("DATA_DIR", "/data"))
DATA.mkdir(parents=True, exist_ok=True)
EVENTS = DATA / "events.jsonl"
WEBHOOK = os.environ.get("ALERT_WEBHOOK_URL", "")
COOLDOWN = int(os.environ.get("ALERT_COOLDOWN_SECONDS", "300"))
MAX_LOG_BYTES = 5_000_000

_last_alert = {}
_lock = threading.Lock()


def record(kind, src, detail=None, alert=True):
    """Write one event to disk and (optionally) alert. Never raises."""
    event = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": kind,
        "src": src,
        "detail": detail or {},
    }
    line = json.dumps(event)
    print(line, flush=True)
    with _lock:
        try:
            if EVENTS.exists() and EVENTS.stat().st_size > MAX_LOG_BYTES:
                EVENTS.replace(DATA / "events.1.jsonl")
            with EVENTS.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as exc:
            print(f"could not write event log: {exc}", flush=True)
    if alert:
        _notify(event)
    return event


def read_events(limit=200):
    try:
        lines = EVENTS.read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return []
    out = []
    for ln in reversed(lines):
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def _notify(event):
    if not WEBHOOK:
        return
    key = (event["kind"], event["src"])
    now = time.time()
    with _lock:
        if now - _last_alert.get(key, 0) < COOLDOWN:
            return  # same kind from same source: don't spam
        _last_alert[key] = now
    text = f"[tripwire] {event['kind']} from {event['src']} {json.dumps(event['detail'])}"
    # "text" works for Slack/Teams-style webhooks, "content" for Discord.
    body = json.dumps({"text": text, "content": text}).encode()

    def post():
        req = urllib.request.Request(WEBHOOK, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception as exc:  # noqa: BLE001 - alert failure must not crash the trap
            print(f"alert failed: {exc}", flush=True)

    threading.Thread(target=post, daemon=True).start()
