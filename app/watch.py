"""The learning core of lan-watchdog.

Every cycle: ARP-scan the local network, compare what answered against what we have
seen before, and raise an event for anything surprising.

  baseline      first ever scan: just learn what is normal (no alert)
  new-device    a MAC address we have never seen before
  arp-conflict  one IP answered by two different MACs (a classic ARP-spoofing sign)
"""
import json
import os
import re
import subprocess
import threading
from datetime import datetime, timezone

from common import DATA, record

DEVICES = DATA / "devices.json"
INTERVAL = int(os.environ.get("SCAN_INTERVAL_SECONDS", "120"))
IFACE = os.environ.get("SCAN_INTERFACE", "")
ROW = re.compile(r"^(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f]{2}(?::[0-9a-f]{2}){5})\s*(.*)$", re.I)

_lock = threading.Lock()      # the scanner thread and the dashboard both touch devices.json
_active_conflicts = set()     # only report a conflict when it first appears, not every scan
LAST_SCAN = None


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def scan():
    """Run arp-scan and return [(ip, mac, vendor)], plus its exit code and stderr."""
    cmd = ["arp-scan", "--localnet"]
    if IFACE:
        cmd += ["--interface", IFACE]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    rows = []
    for line in out.stdout.splitlines():
        m = ROW.match(line)
        if m:
            vendor = re.sub(r"\(DUP: \d+\)", "", m.group(3)).strip()
            rows.append((m.group(1), m.group(2).lower(), vendor))
    return rows, out.returncode, out.stderr.strip()


def load():
    try:
        return json.loads(DEVICES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save(devices):
    tmp = DEVICES.with_suffix(".tmp")
    tmp.write_text(json.dumps(devices, indent=2), encoding="utf-8")
    tmp.replace(DEVICES)


def devices():
    with _lock:
        return load() or {}


def rename(mac, name):
    """Give a known device a friendly name. Returns False if the MAC is unknown."""
    with _lock:
        known = load() or {}
        if mac not in known:
            return False
        known[mac]["name"] = name
        save(known)
        return True


def cycle():
    global LAST_SCAN, _active_conflicts
    rows, code, err = scan()
    if code != 0 and not rows:
        print(f"arp-scan failed ({code}): {err}", flush=True)
        return

    events = []
    with _lock:
        known = load()
        baseline = known is None
        known = known or {}

        seen_ips = {}
        for ip, mac, vendor in rows:
            seen_ips.setdefault(ip, set()).add(mac)
            if mac not in known:
                known[mac] = {"ip": ip, "vendor": vendor, "first_seen": now(), "name": ""}
                if not baseline:
                    events.append(("new-device", ip, {"mac": mac, "vendor": vendor or "unknown"}, True))
            known[mac]["ip"] = ip
            known[mac]["last_seen"] = now()

        conflicts = {(ip, tuple(sorted(macs))) for ip, macs in seen_ips.items() if len(macs) > 1}
        for ip, macs in sorted(conflicts - _active_conflicts):
            events.append(("arp-conflict", ip, {"macs": list(macs)}, True))
        _active_conflicts = conflicts

        if baseline:
            events.append(("baseline", "watcher", {"devices": len(known)}, False))
        save(known)
        LAST_SCAN = now()

    for kind, src, detail, alert in events:
        record(kind, src, detail, alert=alert)
