"""lan-watchdog: scan on a schedule in the background and serve a small dashboard."""
import asyncio
import os
import re

from aiohttp import web

import watch
from common import read_events

PORT = int(os.environ.get("DASHBOARD_PORT", "8088"))
MAC = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")
SHOWN = {"new-device", "arp-conflict", "baseline"}

PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>LAN Watchdog</title>
<style>body{font:15px system-ui;background:#0b1020;color:#e8ecf7;max-width:900px;margin:24px auto;padding:0 16px}
h1{margin:0 0 4px}h2{margin:24px 0 4px}table{width:100%;border-collapse:collapse}td{padding:6px 8px;border-bottom:1px solid #232c47;vertical-align:top}
.bad{color:#ff6b6b;font-weight:600}.warn{color:#ffb454;font-weight:600}.ok{color:#3ddc97}small,.mute{color:#9aa6c7}
button{background:none;border:1px solid #232c47;color:#4fb3ff;border-radius:6px;padding:2px 8px;cursor:pointer}</style>
<h1>LAN Watchdog</h1><small id=meta>Loading...</small>
<h2>Join events</h2><table id=ev></table>
<h2>Devices on the network</h2>
<small>Name every device you recognise. Anything still amber is a device you have not accounted for yet.</small>
<table id=dev></table>
<script>
const KIND={ 'new-device':'warn','arp-conflict':'bad','baseline':'ok' };
const when=s=>(s||'').slice(0,19).replace('T',' ');
function cell(t,c){const td=document.createElement('td');td.textContent=t;if(c)td.className=c;return td}
async function rename(mac,old){
 const name=prompt('Name for '+mac,old||''); if(name===null)return;
 await fetch('/api/rename',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mac,name})}); load();
}
async function load(){
 const [ev,dev,st]=await Promise.all(['/api/events','/api/devices','/api/status'].map(u=>fetch(u).then(r=>r.json())));
 document.getElementById('meta').textContent=st.last_scan?('Last scan '+when(st.last_scan)+' UTC · '+Object.keys(dev).length+' devices known · refreshes every 5s'):'Waiting for the first scan...';
 const e=document.getElementById('ev');e.replaceChildren();
 if(!ev.length){const r=e.insertRow();r.appendChild(cell('Nothing yet. Join the network with a new device to see an event here.','mute'))}
 ev.forEach(x=>{const r=e.insertRow();r.appendChild(cell(when(x.ts),'mute'));r.appendChild(cell(x.kind,KIND[x.kind]));r.appendChild(cell(x.src));r.appendChild(cell(JSON.stringify(x.detail),'mute'))});
 const d=document.getElementById('dev');d.replaceChildren();
 Object.entries(dev).forEach(([mac,v])=>{const r=d.insertRow();
  r.appendChild(cell(v.name||'unnamed',v.name?'':'warn'));r.appendChild(cell(v.ip));r.appendChild(cell(v.vendor||'','mute'));r.appendChild(cell(mac,'mute'));
  r.appendChild(cell('seen '+when(v.last_seen),'mute'));
  const td=document.createElement('td');const b=document.createElement('button');b.textContent='name';b.onclick=()=>rename(mac,v.name);td.appendChild(b);r.appendChild(td)});
}
load();setInterval(load,5000);
</script>"""


async def index(_):
    return web.Response(text=PAGE, content_type="text/html")


async def events(_):
    return web.json_response([e for e in read_events(300) if e["kind"] in SHOWN][:100])


async def devices(_):
    return web.json_response(watch.devices())


async def status(_):
    return web.json_response({"last_scan": watch.LAST_SCAN})


async def rename(request):
    if request.content_type != "application/json":
        return web.json_response({"error": "JSON only"}, status=415)
    try:
        body = await request.json()
    except ValueError:
        return web.json_response({"error": "bad JSON"}, status=400)
    mac = str(body.get("mac", "")).lower()
    name = str(body.get("name", "")).strip()[:40]
    if not MAC.match(mac):
        return web.json_response({"error": "bad MAC"}, status=400)
    if not watch.rename(mac, name):
        return web.json_response({"error": "unknown device"}, status=404)
    return web.json_response({"ok": True})


async def scanner_loop():
    while True:
        try:
            await asyncio.to_thread(watch.cycle)  # arp-scan blocks, so keep it off the event loop
        except Exception as exc:  # noqa: BLE001 - keep watching no matter what
            print(f"scan cycle error: {exc}", flush=True)
        await asyncio.sleep(watch.INTERVAL)


async def start_scanner(app):
    app["scanner"] = asyncio.create_task(scanner_loop())
    yield
    app["scanner"].cancel()


def build_app():
    app = web.Application()
    app.add_routes([
        web.get("/", index),
        web.get("/api/events", events),
        web.get("/api/devices", devices),
        web.get("/api/status", status),
        web.post("/api/rename", rename),
    ])
    app.cleanup_ctx.append(start_scanner)
    return app


if __name__ == "__main__":
    print(f"lan-watchdog up: dashboard on :{PORT}, scanning every {watch.INTERVAL}s", flush=True)
    web.run_app(build_app(), port=PORT, access_log=None, print=None)
