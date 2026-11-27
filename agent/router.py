"""TP-Link EX20v modem erişimi (tplinkrouterc6u kütüphanesi ile).

EX serisi modemler `user` kullanıcı adıyla ve yerel (local) parola ile giriş yapar.
Modem aynı anda tek yönetici oturumuna izin verdiği için her işlem: giriş → işlem → çıkış.
"""
from __future__ import annotations

import ssl
import threading
import urllib.request

import credentials

try:
    from tplinkrouterc6u import (Connection, TPLinkEXClient, TPLinkEXClientGCM,
                                 TPLinkEXClientGCMOAEP, TplinkRouterProvider)
    AVAILABLE = True
except Exception:  # kütüphane yoksa ajan yine çalışır, yalnızca modem kontrolü kapanır
    AVAILABLE = False

_lock = threading.Lock()
_cls_cache: dict[str, type] = {}

WIFI_MAP = {
    "host_2g": "HOST_2G", "host_5g": "HOST_5G",
    "guest_2g": "GUEST_2G", "guest_5g": "GUEST_5G",
}


class RouterError(Exception):
    pass


def _url(host: str) -> str:
    return host if host.startswith("http") else f"http://{host}"


def _candidates():
    return [TPLinkEXClient, TPLinkEXClientGCM, TPLinkEXClientGCMOAEP]


def _connect(cfg: dict):
    if not AVAILABLE:
        raise RouterError("tplinkrouterc6u kurulu değil (pip install -r agent/requirements.txt)")
    host, user, pw = _url(cfg.get("router_host") or "192.168.1.1"), cfg.get("router_user") or "user", cfg.get("router_password")
    if not pw:
        raise RouterError("Modem parolası ayarlanmamış")
    key = host
    errors = []
    order = ([_cls_cache[key]] if key in _cls_cache else []) + [c for c in _candidates() if c is not _cls_cache.get(key)]
    for cls in order:
        try:
            r = cls(host, pw, user, timeout=15)
            r.authorize()
            _cls_cache[key] = cls
            return r
        except Exception as e:  # noqa: BLE001
            errors.append(f"{cls.__name__}: {e}")
    try:  # son çare: kütüphanenin otomatik seçimi
        r = TplinkRouterProvider.get_client(host, pw, user, timeout=15)
        r.authorize()
        _cls_cache[key] = type(r)
        return r
    except Exception as e:  # noqa: BLE001
        errors.append(f"Provider: {e}")
    raise RouterError("Modeme giriş yapılamadı. Parolayı ve kullanıcı adını (EX serisi: user) kontrol edin. "
                      + " | ".join(errors[-2:]))


def _session(cfg: dict, fn):
    with _lock:
        r = _connect(cfg)
        try:
            return fn(r)
        finally:
            try:
                r.logout()
            except Exception:  # noqa: BLE001
                pass


def _conn_name(t) -> str:
    return getattr(t, "value", str(t)) if t is not None else "unknown"


def status(cfg: dict) -> dict:
    def fn(r):
        s = r.get_status()
        fw = None
        try:
            f = r.get_firmware()
            fw = {"model": getattr(f, "model", None), "hardware": getattr(f, "hardware_version", None),
                  "firmware": getattr(f, "firmware_version", None)}
        except Exception:  # noqa: BLE001
            pass
        devices = [{
            "mac": d.macaddr.replace("-", ":").lower(), "ip": d.ipaddr, "hostname": d.hostname or "",
            "type": _conn_name(d.type), "signal": d.signal, "active": d.active,
            "down_speed": d.down_speed, "up_speed": d.up_speed,
        } for d in (s.devices or [])]
        return {
            "client": type(r).__name__,
            "firmware": fw,
            "wan_ip": s.wan_ipv4_addr, "lan_ip": s.lan_ipv4_addr, "wan_uptime": s.wan_ipv4_uptime,
            "conn_type": s.conn_type, "cpu": s.cpu_usage, "mem": s.mem_usage,
            "clients_total": s.clients_total, "wifi_clients": s.wifi_clients_total,
            "wired_clients": s.wired_total, "guest_clients": s.guest_clients_total,
            "wifi": {"host_2g": s.wifi_2g_enable, "host_5g": s.wifi_5g_enable,
                     "guest_2g": s.guest_2g_enable, "guest_5g": s.guest_5g_enable},
            "devices": devices,
            "can_block": hasattr(r, "block_device"),
        }
    return _session(cfg, fn)


def set_wifi(cfg: dict, band: str, enable: bool) -> None:
    if band not in WIFI_MAP:
        raise RouterError("Geçersiz bant")
    _session(cfg, lambda r: r.set_wifi(getattr(Connection, WIFI_MAP[band]), enable))


def reboot(cfg: dict) -> None:
    _session(cfg, lambda r: r.reboot())


def block(cfg: dict, mac: str, name: str = "", unblock: bool = False) -> bool:
    """Modem destekliyorsa kara listeye ekler. Desteklemiyorsa False döner (arayüz menü yolunu gösterir)."""
    def fn(r):
        if unblock:
            if not hasattr(r, "unblock_device"):
                return False
            r.unblock_device(mac)
            return True
        if not hasattr(r, "block_device"):
            return False
        r.block_device(mac, name)
        return True
    return _session(cfg, fn)


# ---------------------------------------------------------------- marka algılama + varsayılan giriş
def detect_brand(host: str, timeout: float = 4.0) -> dict:
    """Modem giriş sayfasını (LAN'da, proxy'siz) çekip markayı tahmin eder."""
    url = _url(host)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    body, hdr = "", ""
    reachable = False
    for u in ([url] if url.startswith("https") else [url, url.replace("http://", "https://", 1)]):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "ex20v-agent"})
            # LAN modemine gidildiği için sistem/çevre proxy'si atlanır.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                                 urllib.request.HTTPSHandler(context=ctx))
            with opener.open(req, timeout=timeout) as r:
                reachable = True
                hdr = " ".join(f"{k}:{v}" for k, v in r.headers.items())
                body = r.read(60000).decode("utf-8", "replace")
            break
        except Exception:  # noqa: BLE001
            continue
    return {"reachable": reachable, "brand": credentials.detect_brand(body, hdr)}


def try_login(cfg: dict, extra: list | None = None) -> dict:
    """Varsayılan kullanıcı adı/parolaları sırayla deneyip ilk çalışanı bildirir.

    Parolayı KAYDETMEZ; yalnızca hangi bilgilerle girilebildiğini döndürür. Çalışan
    bir varsayılan bulunursa güvenlik uyarısı (is_default) ile birlikte verir.
    """
    host = cfg.get("router_host") or "192.168.1.1"
    det = detect_brand(host)
    if not det["reachable"]:
        raise RouterError("Modeme ulaşılamadı. Aynı ağda ve adresin doğru olduğundan emin olun.")
    tried = 0
    for user, pw, note in credentials.candidates(det.get("brand"), extra):
        tried += 1
        if tried > 14:  # modemi kilitlememek için deneme sayısını sınırla
            break
        test = {**cfg, "router_user": user, "router_password": pw}
        try:
            info = status(test)
        except Exception:  # noqa: BLE001
            continue
        return {
            "found": True, "username": user, "password": pw, "note": note,
            "brand": det.get("brand"), "is_default": credentials.is_default(user, pw),
            "firmware": info.get("firmware"), "client": info.get("client"), "tried": tried,
        }
    return {"found": False, "brand": det.get("brand"), "tried": tried}
