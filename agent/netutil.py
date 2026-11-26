"""Ağ yardımcıları: komut çalıştırma, ping, ARP, alt ağ taraması, DNS kıyası, OUI, Wi-Fi taraması."""
from __future__ import annotations

import concurrent.futures as cf
import ipaddress
import os
import platform
import random
import re
import socket
import statistics
import struct
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

IS_WIN = platform.system() == "Windows"
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)
_NO_WINDOW = 0x08000000 if IS_WIN else 0


def _oem_encoding() -> str:
    if IS_WIN:
        try:
            import ctypes
            return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
        except Exception:
            return "cp857"
    return "utf-8"


ENC = _oem_encoding()


def run(cmd: list[str], timeout: float = 20) -> str:
    """Komutu çalıştırır, Windows konsol kod sayfasıyla çözer; hata olursa boş metin döner."""
    try:
        raw = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=_NO_WINDOW).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""
    for enc in (ENC, "utf-8", "cp1254"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


# ---------------------------------------------------------------- yerel IP / ağ geçidi
def local_ip(target: str = "192.168.1.1") -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((target, 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


# ---------------------------------------------------------------- ping
_TIME = re.compile(r"[=<]\s*([\d]+(?:[.,]\d+)?)\s*ms", re.I)


def parse_ping(text: str) -> list[float]:
    """Yanıt satırlarındaki gecikmeleri (ms) döndürür. 'time<1ms' / 'süre<1ms' → 1.0 sayılır."""
    out = []
    for line in text.splitlines():
        if "ttl" not in line.lower():
            continue
        m = _TIME.search(line)
        if m:
            out.append(float(m.group(1).replace(",", ".")))
    return out


def ping(host: str, count: int = 10, timeout_ms: int = 1000) -> dict:
    count = max(1, min(count, 50))
    if IS_WIN:
        cmd = ["ping", "-n", str(count), "-w", str(timeout_ms), host]
    else:
        cmd = ["ping", "-c", str(count), "-i", "0.3", "-W", str(max(1, timeout_ms // 1000)), host]
    times = parse_ping(run(cmd, timeout=count * (timeout_ms / 1000 + 1.5) + 5))
    return summarize(times, count)


def summarize(times: list[float], sent: int) -> dict:
    loss = round(100 * (sent - len(times)) / sent, 1) if sent else 0.0
    if not times:
        return {"sent": sent, "received": 0, "loss": 100.0, "avg": None, "min": None, "max": None, "jitter": None}
    jit = statistics.mean(abs(a - b) for a, b in zip(times, times[1:])) if len(times) > 1 else 0.0
    return {"sent": sent, "received": len(times), "loss": max(loss, 0.0),
            "avg": round(statistics.mean(times), 2), "min": min(times), "max": max(times),
            "jitter": round(jit, 2)}


def _ping_once(ip: str) -> bool:
    cmd = ["ping", "-n", "1", "-w", "400", ip] if IS_WIN else ["ping", "-c", "1", "-W", "1", ip]
    return bool(parse_ping(run(cmd, timeout=3)))


# ---------------------------------------------------------------- ARP / tarama
_ARP_WIN = re.compile(r"^\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f]{2}(?:-[0-9a-f]{2}){5})\s", re.I | re.M)
_ARP_LNX = re.compile(r"^(\d+\.\d+\.\d+\.\d+)\s.*lladdr\s+([0-9a-f:]{17})", re.I | re.M)


def norm_mac(mac: str) -> str:
    return mac.replace("-", ":").lower()


def parse_arp(text: str) -> dict[str, str]:
    """ARP tablosu → {ip: mac}. Yayın / çoklu yayın adresleri atlanır."""
    res = {}
    for ip, mac in _ARP_WIN.findall(text) + _ARP_LNX.findall(text):
        mac = norm_mac(mac)
        if mac in ("ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00") or mac.startswith("01:00:5e"):
            continue
        res[ip] = mac
    return res


def arp_table() -> dict[str, str]:
    return parse_arp(run(["arp", "-a"]) if IS_WIN else run(["ip", "neigh"]))


def _hostname(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except OSError:
        return ""


def scan(subnet: str) -> list[dict]:
    """Ping taraması + ARP + ters DNS. Ping'e yanıt vermeyen cihazlar ARP'ta görünürse yine listelenir."""
    net = ipaddress.ip_network(subnet, strict=False)
    hosts = [str(h) for h in net.hosts()][:1024]
    with cf.ThreadPoolExecutor(max_workers=64) as ex:
        alive = dict(zip(hosts, ex.map(_ping_once, hosts)))
    table = {ip: mac for ip, mac in arp_table().items() if ipaddress.ip_address(ip) in net}
    me = local_ip(str(next(net.hosts())))
    mine = {me} if ipaddress.ip_address(me) in net else set()
    ips = sorted(set(table) | {ip for ip, ok in alive.items() if ok} | mine,
                 key=lambda x: ipaddress.ip_address(x))
    with cf.ThreadPoolExecutor(max_workers=32) as ex:
        names = dict(zip(ips, ex.map(_hostname, ips)))
    out = []
    for ip in ips:
        mac = table.get(ip, "")
        if ip == me and not mac:
            mac = own_mac()
        name = names.get(ip, "") or (socket.gethostname() if ip == me else "")
        out.append({"ip": ip, "mac": mac, "hostname": name, "self": ip == me})
    return out


def own_mac() -> str:
    import uuid
    n = uuid.getnode()
    return ":".join(f"{(n >> s) & 0xff:02x}" for s in range(40, -1, -8))


def is_random_mac(mac: str) -> bool:
    """Yerel yönetimli (rastgele / özel) MAC: ilk baytın 2. biti 1."""
    try:
        return bool(int(mac[:2], 16) & 0x02)
    except ValueError:
        return False


# ---------------------------------------------------------------- OUI (üretici)
MANUF_URL = "https://www.wireshark.org/download/automated/data/manuf"
MANUF_FILE = DATA_DIR / "manuf.txt"
_oui: dict[str, str] = {}
_oui_lock = threading.Lock()


def _load_manuf() -> None:
    if not MANUF_FILE.exists():
        return
    tmp = {}
    for line in MANUF_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and len(parts[0]) == 8:  # yalnızca /24 önekler
            tmp[parts[0].upper()] = (parts[2] if len(parts) > 2 and parts[2] else parts[1]).strip()
    with _oui_lock:
        _oui.clear()
        _oui.update(tmp)


def ensure_oui(max_age_days: int = 30) -> None:
    """Üretici listesini (Wireshark manuf) indirir ve önbelleğe alır. MAC adresleri dışarı gönderilmez."""
    fresh = MANUF_FILE.exists() and time.time() - MANUF_FILE.stat().st_mtime < max_age_days * 86400
    if not fresh:
        try:
            req = urllib.request.Request(MANUF_URL, headers={"User-Agent": "ex20v-agent"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read()
            if len(data) > 100_000:
                MANUF_FILE.write_bytes(data)
        except Exception:
            pass
    _load_manuf()


def vendor(mac: str) -> str:
    if not mac:
        return ""
    if is_random_mac(mac):
        return "Özel (rastgele) MAC"
    with _oui_lock:
        return _oui.get(mac[:8].upper(), "")


# ---------------------------------------------------------------- DNS kıyası
DNS_SERVERS = {"Cloudflare": "1.1.1.1", "Google": "8.8.8.8", "Quad9": "9.9.9.9"}
DNS_DOMAINS = ["google.com", "youtube.com", "instagram.com", "whatsapp.net", "netflix.com",
               "trendyol.com", "hepsiburada.com", "eksisozluk.com", "sahibinden.com", "wikipedia.org"]


def _dns_query(server: str, domain: str, timeout: float = 2.0) -> float | None:
    tid = random.randint(0, 0xFFFF)
    q = struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 0)
    q += b"".join(bytes([len(p)]) + p.encode() for p in domain.split(".")) + b"\x00"
    q += struct.pack(">HH", 1, 1)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        t0 = time.perf_counter()
        s.sendto(q, (server, 53))
        while True:
            data, _ = s.recvfrom(1024)
            if len(data) >= 2 and struct.unpack(">H", data[:2])[0] == tid:
                return round((time.perf_counter() - t0) * 1000, 1)
    except OSError:
        return None
    finally:
        s.close()


def system_dns() -> str | None:
    if IS_WIN:
        txt = run(["ipconfig", "/all"])
        lines = txt.splitlines()
        for i, line in enumerate(lines):
            if "DNS" in line and ":" in line:
                # IPv6 ilk sırada olabilir; devam satırlarına da bak
                for cand in [line] + [l for l in lines[i + 1:i + 4] if " : " not in l]:
                    m = re.search(r"(\d+\.\d+\.\d+\.\d+)\s*$", cand)
                    if m:
                        return m.group(1)
        return None
    try:
        for line in Path("/etc/resolv.conf").read_text().splitlines():
            if line.startswith("nameserver"):
                ip = line.split()[1]
                if re.match(r"^\d+\.\d+\.\d+\.\d+$", ip) and not ip.startswith("127."):
                    return ip
    except OSError:
        pass
    return None


def dns_benchmark() -> list[dict]:
    servers = dict(DNS_SERVERS)
    sysdns = system_dns()
    if sysdns and sysdns not in servers.values():
        servers = {f"Mevcut ({sysdns})": sysdns, **servers}
    elif sysdns:
        servers = {(k + " (mevcut)" if v == sysdns else k): v for k, v in servers.items()}

    def bench(item):
        name, ip = item
        times = [t for d in DNS_DOMAINS if (t := _dns_query(ip, d)) is not None]
        return {"name": name, "ip": ip, "current": ip == sysdns,
                "median": round(statistics.median(times), 1) if times else None,
                "ok": len(times), "total": len(DNS_DOMAINS)}

    with cf.ThreadPoolExecutor(max_workers=len(servers)) as ex:
        res = list(ex.map(bench, servers.items()))
    return sorted(res, key=lambda r: (r["median"] is None, r["median"] or 0))


# ---------------------------------------------------------------- Wi-Fi taraması tetikleme (Windows)
def trigger_wlan_scan(wait: float = 4.0) -> bool:
    """WlanScan çağırır; netsh yalnızca önbelleği okuduğu için taze sonuç almayı sağlar."""
    if not IS_WIN:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        wlan = ctypes.windll.wlanapi

        class GUID(ctypes.Structure):
            _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD), ("d3", wintypes.WORD), ("d4", ctypes.c_ubyte * 8)]

        class INFO(ctypes.Structure):
            _fields_ = [("guid", GUID), ("desc", ctypes.c_wchar * 256), ("state", wintypes.DWORD)]

        class LIST(ctypes.Structure):
            _fields_ = [("n", wintypes.DWORD), ("idx", wintypes.DWORD), ("items", INFO * 16)]

        h = wintypes.HANDLE()
        ver = wintypes.DWORD()
        if wlan.WlanOpenHandle(2, None, ctypes.byref(ver), ctypes.byref(h)) != 0:
            return False
        plist = ctypes.POINTER(LIST)()
        try:
            if wlan.WlanEnumInterfaces(h, None, ctypes.byref(plist)) != 0:
                return False
            n = plist.contents.n
            for i in range(min(n, 16)):
                wlan.WlanScan(h, ctypes.byref(plist.contents.items[i].guid), None, None, None)
            wlan.WlanFreeMemory(plist)
        finally:
            wlan.WlanCloseHandle(h, None)
        time.sleep(wait)
        return n > 0
    except Exception:
        return False


def open_location_settings() -> None:
    if IS_WIN:
        try:
            os.startfile("ms-settings:privacy-location")  # type: ignore[attr-defined]
        except OSError:
            pass
