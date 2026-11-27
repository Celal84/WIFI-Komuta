"""EX20v Ağ Kontrol Merkezi — yerel Windows ajanı.

Çalıştırma:  python agent/server.py   (veya baslat.bat)
API + arayüz: http://<PC-IP>:8080
"""
from __future__ import annotations

import json
import os
import platform
import secrets
import socket
import sqlite3
import sys
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
import netsh_parser  # noqa: E402
import netutil  # noqa: E402
import router  # noqa: E402

VERSION = "1.1.0"
APP_NAME = "EX20v Ağ Kontrol Merkezi"
HOME_TITLE = "Ev Ağım"  # telefonda Ana Ekran simgesinin adı (internet sürümü: "Ağ Kontrol")
AGENT_DIR = Path(__file__).resolve().parent
ROOT = AGENT_DIR.parent
DB_PATH = AGENT_DIR / "data" / "ex20v.db"
CFG_PATH = AGENT_DIR / "data" / "config.json"
PORT = int(os.environ.get("EX20V_PORT", "8080"))

# Yalnızca bu kaynaklar ajanın yanıtlarını okuyabilir (diğer sitelerin cihaz listesini çekmesini engeller).
ALLOWED_ORIGINS = {
    "https://celal84.github.io",
    f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}",
}
ALLOWED_ORIGINS |= {o.strip() for o in os.environ.get("EX20V_ORIGINS", "").split(",") if o.strip()}

# Sunulacak arayüz dosyaları (repo kökünün tamamı değil — config ve veritabanı dışarı açılmaz).
STATIC = {"": "index.html", "index.html": "index.html", "manifest.json": "manifest.json", "sw.js": "sw.js",
          "icons/icon-192.png": "icons/icon-192.png", "icons/icon-512.png": "icons/icon-512.png",
          "icons/apple-touch-icon.png": "icons/apple-touch-icon.png"}


# ---------------------------------------------------------------- yapılandırma
def load_cfg() -> dict:
    cfg = {}
    if CFG_PATH.exists():
        try:
            cfg = json.loads(CFG_PATH.read_text(encoding="utf-8"))
        except ValueError:
            cfg = {}
    changed = False
    if not cfg.get("agent_key"):
        cfg["agent_key"] = f"{secrets.randbelow(10**6):06d}"
        changed = True
    cfg.setdefault("router_host", "192.168.1.1")
    cfg.setdefault("router_user", "user")
    cfg.setdefault("subnet", "192.168.1.0/24")
    if changed:
        save_cfg(cfg)
    return cfg


def save_cfg(cfg: dict) -> None:
    CFG_PATH.parent.mkdir(exist_ok=True)
    CFG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


CFG = load_cfg()


# ---------------------------------------------------------------- veritabanı
def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS devices(
            mac TEXT PRIMARY KEY, name TEXT DEFAULT '', category TEXT DEFAULT '', trusted INTEGER DEFAULT 0,
            hostname TEXT DEFAULT '', vendor TEXT DEFAULT '', last_ip TEXT DEFAULT '',
            first_seen REAL, last_seen REAL);
        CREATE TABLE IF NOT EXISTS measurements(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, data TEXT);
        """)


init_db()


# ---------------------------------------------------------------- uygulama
app = FastAPI(title=APP_NAME, version=VERSION, docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.middleware("http")
async def cors(request: Request, call_next):
    origin = request.headers.get("origin")
    ok = origin in ALLOWED_ORIGINS or (origin and _same_host(origin, request))
    if request.method == "OPTIONS" and request.headers.get("access-control-request-method"):
        resp = Response(status_code=204 if ok else 403)
    elif origin and not ok and request.method not in ("GET", "HEAD"):
        # Başka sitelerden gelen "basit" POST isteklerini (CSRF) reddet
        resp = JSONResponse(status_code=403, content={"detail": "Bu kaynaktan erişime izin yok"})
    else:
        resp = await call_next(request)
    if ok:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Agent-Key"
        resp.headers["Access-Control-Max-Age"] = "600"
        # Chrome "Private/Local Network Access" ön kontrolü (HTTPS sayfadan localhost'a istek)
        if request.headers.get("access-control-request-private-network"):
            resp.headers["Access-Control-Allow-Private-Network"] = "true"
    return resp


def _same_host(origin: str, request: Request) -> bool:
    return origin.rstrip("/") == f"{request.url.scheme}://{request.headers.get('host', '')}"


def _is_loopback(request: Request) -> bool:
    return (request.client.host if request.client else "") in ("127.0.0.1", "::1", "localhost")


def require_key(request: Request) -> None:
    """Modemi değiştiren işlemler anahtar ister. Aynı PC'den (localhost) gelen isteklerde gerekmez."""
    if _is_loopback(request):
        return
    if request.headers.get("x-agent-key") != CFG["agent_key"]:
        raise HTTPException(401, "Ajan anahtarı gerekli (baslat.bat penceresinde yazıyor)")


def router_call(fn, *a, **kw):
    try:
        return fn(CFG, *a, **kw)
    except router.RouterError as e:
        raise HTTPException(502, str(e)) from e
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Modem hatası: {e}") from e


# ---------------------------------------------------------------- genel
@app.get("/api/health")
def health(request: Request):
    return {
        "ok": True, "app": APP_NAME, "version": VERSION, "platform": platform.system(),
        "hostname": socket.gethostname(), "pc_ip": netutil.local_ip(CFG["router_host"]), "port": PORT,
        "router_host": CFG["router_host"], "router_configured": bool(CFG.get("router_password")),
        "router_lib": router.AVAILABLE, "wifi_supported": netutil.IS_WIN,
        "key_required": not _is_loopback(request),
    }


@app.get("/api/key")
def key(request: Request):
    """Anahtar yalnızca ajanın çalıştığı PC'ye verilir."""
    if not _is_loopback(request):
        raise HTTPException(403, "Yalnızca ajanın çalıştığı bilgisayardan alınabilir")
    return {"key": CFG["agent_key"]}


@app.get("/api/ping")
def api_ping(host: str | None = None, count: int = 10):
    host = host or CFG["router_host"]
    if not all(c.isalnum() or c in ".-:" for c in host):
        raise HTTPException(400, "Geçersiz adres")
    return {"host": host, **netutil.ping(host, count)}


@app.get("/api/dns")
def api_dns():
    return {"results": netutil.dns_benchmark()}


# ---------------------------------------------------------------- cihazlar
class DeviceMeta(BaseModel):
    name: str | None = None
    category: str | None = None
    trusted: bool | None = None


@app.get("/api/devices")
def api_devices():
    now = time.time()
    found: dict[str, dict] = {}
    for d in netutil.scan(CFG["subnet"]):
        if d["mac"]:
            found[d["mac"]] = {**d, "source": "tarama"}

    router_info, router_err = None, None
    if CFG.get("router_password"):
        try:
            router_info = router.status(CFG)
            for rd in router_info["devices"]:
                cur = found.get(rd["mac"], {"self": False})
                found[rd["mac"]] = {**cur, "ip": rd["ip"] or cur.get("ip", ""), "mac": rd["mac"],
                                    "hostname": rd["hostname"] or cur.get("hostname", ""),
                                    "type": rd["type"], "signal": rd["signal"], "source": "modem"}
        except Exception as e:  # noqa: BLE001
            router_err = str(e)

    out = []
    with db() as con:
        known = {r["mac"]: dict(r) for r in con.execute("SELECT * FROM devices")}
        for mac, d in found.items():
            k = known.get(mac)
            vend = netutil.vendor(mac)
            if k is None:
                con.execute("INSERT INTO devices(mac, hostname, vendor, last_ip, first_seen, last_seen) VALUES(?,?,?,?,?,?)",
                            (mac, d.get("hostname", ""), vend, d.get("ip", ""), now, now))
                k = {"name": "", "category": "", "trusted": 0, "first_seen": now}
            else:
                con.execute("UPDATE devices SET hostname=COALESCE(NULLIF(?,''),hostname), vendor=?, last_ip=?, last_seen=? WHERE mac=?",
                            (d.get("hostname", ""), vend, d.get("ip", ""), now, mac))
            is_gw = d.get("ip") == CFG["router_host"]
            out.append({
                **d, "vendor": vend, "random_mac": netutil.is_random_mac(mac),
                "name": k["name"] or ("EX20v Modem" if is_gw else ""), "category": k["category"] or ("Modem" if is_gw else ""),
                "trusted": bool(k["trusted"]) or is_gw or d.get("self", False),
                "first_seen": k["first_seen"], "online": True,
            })
        seen = set(found)
        for mac, k in known.items():  # şu an çevrimdışı olan bilinen cihazlar
            if mac not in seen:
                out.append({"mac": mac, "ip": k["last_ip"], "hostname": k["hostname"], "vendor": k["vendor"],
                            "random_mac": netutil.is_random_mac(mac), "name": k["name"], "category": k["category"],
                            "trusted": bool(k["trusted"]), "first_seen": k["first_seen"], "last_seen": k["last_seen"],
                            "online": False, "self": False})
    out.sort(key=lambda d: (not d["online"], tuple(int(x) for x in (d.get("ip") or "999.0.0.0").split("."))))
    return {"devices": out, "router": bool(router_info), "router_error": router_err,
            "can_block": bool(router_info and router_info.get("can_block")), "scanned_at": now}


@app.put("/api/devices/{mac}")
def api_device_update(mac: str, meta: DeviceMeta):
    mac = netutil.norm_mac(mac)
    with db() as con:
        if not con.execute("SELECT 1 FROM devices WHERE mac=?", (mac,)).fetchone():
            con.execute("INSERT INTO devices(mac, first_seen, last_seen) VALUES(?,?,?)", (mac, time.time(), time.time()))
        for field in ("name", "category"):
            v = getattr(meta, field)
            if v is not None:
                con.execute(f"UPDATE devices SET {field}=? WHERE mac=?", (v.strip()[:60], mac))
        if meta.trusted is not None:
            con.execute("UPDATE devices SET trusted=? WHERE mac=?", (int(meta.trusted), mac))
    return {"ok": True}


@app.delete("/api/devices/{mac}")
def api_device_delete(mac: str):
    with db() as con:
        con.execute("DELETE FROM devices WHERE mac=?", (netutil.norm_mac(mac),))
    return {"ok": True}


# ---------------------------------------------------------------- Wi-Fi
@app.get("/api/wifi")
def api_wifi(refresh: bool = True):
    if not netutil.IS_WIN:
        raise HTTPException(501, "Wi-Fi kanal analizi yalnızca Windows'ta çalışır")
    if refresh:
        netutil.trigger_wlan_scan()
    itxt = netutil.run(["netsh", "wlan", "show", "interfaces"])
    ntxt = netutil.run(["netsh", "wlan", "show", "networks", "mode=bssid"])
    ifaces = netsh_parser.parse_interfaces(itxt)
    nets = netsh_parser.parse_networks(ntxt)
    if not nets and netsh_parser.needs_location_permission(ntxt + itxt):
        netutil.open_location_settings()
        return JSONResponse(status_code=409, content={
            "error": "location_permission",
            "detail": "Windows konum izni kapalı. Ayarlar > Gizlilik ve güvenlik > Konum: 'Konum hizmetleri' ve "
                      "'Masaüstü uygulamalarının konumunuza erişmesine izin ver' seçeneklerini açın."})
    if not ifaces:
        return JSONResponse(status_code=404, content={
            "error": "no_wifi", "detail": "Bu bilgisayarda Wi-Fi bağdaştırıcısı bulunamadı (kablolu bağlantıda kanal analizi yapılamaz)."})
    conn = next((i for i in ifaces if i.get("connected")), ifaces[0])
    own_bssids = {n["bssid"] for n in nets if conn.get("ssid") and n["ssid"] == conn["ssid"]}
    rec = netsh_parser.recommend(nets, conn.get("ssid"), own_bssids)
    same_ssid_5g = any(n["band"] == "5" for n in nets if n["bssid"] in own_bssids)
    return {"interface": conn, "networks": nets, "recommendation": rec,
            "smart_connect_warning": conn.get("band") == "2.4",
            "own_5g_visible": same_ssid_5g}


# ---------------------------------------------------------------- modem kontrolü
class RouterCfg(BaseModel):
    host: str = "192.168.1.1"
    username: str = "user"
    password: str


class WifiToggle(BaseModel):
    band: str
    enable: bool


class MacBody(BaseModel):
    mac: str
    name: str = ""


@app.post("/api/router/config")
def api_router_config(body: RouterCfg, request: Request):
    require_key(request)
    test = {**CFG, "router_host": body.host.strip(), "router_user": body.username.strip() or "user",
            "router_password": body.password}
    try:
        info = router.status(test)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e)) from e
    CFG.update({k: test[k] for k in ("router_host", "router_user", "router_password")})
    save_cfg(CFG)
    return {"ok": True, "client": info["client"], "firmware": info["firmware"]}


@app.delete("/api/router/config")
def api_router_forget(request: Request):
    require_key(request)
    CFG.pop("router_password", None)
    save_cfg(CFG)
    return {"ok": True}


@app.get("/api/router/status")
def api_router_status():
    if not CFG.get("router_password"):
        raise HTTPException(412, "Modem bağlantısı ayarlanmamış")
    return router_call(router.status)


@app.post("/api/router/wifi")
def api_router_wifi(body: WifiToggle, request: Request):
    require_key(request)
    router_call(router.set_wifi, body.band, body.enable)
    return {"ok": True}


@app.post("/api/router/reboot")
def api_router_reboot(request: Request):
    require_key(request)
    router_call(router.reboot)
    return {"ok": True}


@app.post("/api/router/block")
def api_router_block(body: MacBody, request: Request):
    require_key(request)
    done = router_call(router.block, netutil.norm_mac(body.mac), body.name)
    return {"ok": done, "fallback": not done}


@app.post("/api/router/unblock")
def api_router_unblock(body: MacBody, request: Request):
    require_key(request)
    done = router_call(router.block, netutil.norm_mac(body.mac), unblock=True)
    return {"ok": done, "fallback": not done}


# ---------------------------------------------------------------- geçmiş
@app.get("/api/history")
def api_history(limit: int = 200):
    with db() as con:
        rows = con.execute("SELECT id, ts, data FROM measurements ORDER BY ts DESC LIMIT ?", (min(limit, 2000),)).fetchall()
    return {"items": [{"id": r["id"], "ts": r["ts"], **json.loads(r["data"])} for r in rows]}


@app.post("/api/history")
async def api_history_add(request: Request):
    body = await request.json()
    items = body if isinstance(body, list) else [body]
    with db() as con:
        for it in items[:2000]:
            if not isinstance(it, dict):
                continue
            try:
                ts = float(it.pop("ts", 0)) or time.time() * 1000  # milisaniye
            except (TypeError, ValueError):
                ts = time.time() * 1000
            it.pop("id", None)
            con.execute("INSERT INTO measurements(ts, data) VALUES(?,?)", (ts, json.dumps(it, ensure_ascii=False)))
    return {"ok": True, "count": len(items)}


@app.delete("/api/history/{mid}")
def api_history_delete(mid: int):
    with db() as con:
        con.execute("DELETE FROM measurements WHERE id=?", (mid,))
    return {"ok": True}


# ---------------------------------------------------------------- arayüz dosyaları
@app.get("/{path:path}")
def static(path: str):
    rel = STATIC.get(path)
    if rel is None:
        raise HTTPException(404)
    f = ROOT / rel
    if not f.exists():
        raise HTTPException(404)
    headers = {"Cache-Control": "no-cache"}
    if rel == "index.html":
        # Ana Ekrana eklenen simge, internet sürümünden ayırt edilsin diye farklı adlandırılır.
        html = f.read_text(encoding="utf-8").replace(
            'name="apple-mobile-web-app-title" content="Ağ Kontrol"',
            f'name="apple-mobile-web-app-title" content="{HOME_TITLE}"')
        return Response(html, media_type="text/html; charset=utf-8", headers=headers)
    if rel == "manifest.json":
        # start_url/scope verilmez: Ana Ekrana eklenen simge, QR ile gelinen adresi
        # (eşleştirme anahtarıyla birlikte) açar.
        man = json.loads(f.read_text(encoding="utf-8"))
        man.pop("start_url", None)
        man.pop("scope", None)
        man.update({"name": f"{HOME_TITLE} — {APP_NAME}", "short_name": HOME_TITLE})
        return Response(json.dumps(man, ensure_ascii=False), media_type="application/manifest+json", headers=headers)
    return FileResponse(f, headers=headers)


def main() -> None:
    threading.Thread(target=netutil.ensure_oui, daemon=True).start()
    ip = netutil.local_ip(CFG["router_host"])
    print(f"\n  {APP_NAME} ajanı v{VERSION}")
    print(f"  Bu bilgisayar : http://localhost:{PORT}")
    print(f"  Telefon       : açılan sayfadaki QR kodu okutun  (veya http://{ip}:{PORT})")
    print(f"  Eşleştirme anahtarı: {CFG['agent_key']}  (QR okutulursa gerekmez)")
    print("  Telefondan kullanmak için bu pencere açık kalmalı.\n")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
