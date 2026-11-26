"""Windows `netsh wlan` çıktılarını (Türkçe / İngilizce) ayrıştırır ve kanal önerisi üretir."""
from __future__ import annotations

import re

# Anahtar eşleştirme: küçük harfe çevrilmiş anahtar bu öneklerden biriyle başlarsa alan adına eşlenir.
# Kod sayfası hatasında Türkçe karakterler bozulabileceği için ASCII önekler kullanılır.
_KEYS = {
    "name": ("name", "ad"),
    "state": ("state", "durum"),
    "ssid": ("ssid",),
    "bssid": ("ap bssid", "bssid"),
    "band": ("band", "bant"),
    "channel": ("channel", "kanal"),
    "radio": ("radio", "radyo"),
    "auth": ("authentication", "kimlik"),
    "signal": ("signal", "sinyal"),
    "rx": ("receive rate", "alma h"),
    "tx": ("transmit rate", "iletim h"),
    "description": ("description", "açıklama", "aciklama"),
}
# Tam eşleşme isteyen alanlar
_EXACT = {"name", "ssid", "channel", "band", "signal", "state"}
_KV = re.compile(r"^\s*([^:]+?)\s*:\s(.*)$")
_MAC = re.compile(r"([0-9a-f]{2}(?::[0-9a-f]{2}){5})", re.I)


def _field(key: str) -> str | None:
    k = key.strip().lower()
    # "SSID 1", "BSSID 2" gibi numaralı başlıklar
    if re.match(r"^bssid\s+\d+$", k):
        return "bssid_item"
    if re.match(r"^ssid\s+\d+$", k):
        return "ssid_item"
    if k.startswith("ap bssid"):
        return "bssid"
    for field, prefixes in _KEYS.items():
        for p in prefixes:
            if field in _EXACT:
                if k == p:
                    return field
                continue  # "Kanal Kullanımı", "Channel Utilization" vb. karışmasın
            if k.startswith(p):
                return field
    return None


def _int(text: str) -> int | None:
    m = re.search(r"\d+", text or "")
    return int(m.group()) if m else None


def band_of(channel: int | None, band_text: str = "") -> str | None:
    t = (band_text or "").replace(",", ".")
    if "2.4" in t:
        return "2.4"
    if t.strip().startswith("6"):
        return "6"
    if "5" in t:
        return "5"
    if channel is None:
        return None
    return "2.4" if channel <= 14 else "5"


def parse_interfaces(text: str) -> list[dict]:
    """`netsh wlan show interfaces` çıktısı → arabirim listesi."""
    out: list[dict] = []
    cur: dict | None = None
    for line in text.splitlines():
        m = _KV.match(line)
        if not m:
            continue
        f = _field(m.group(1))
        val = m.group(2).strip()
        if f == "name":
            cur = {"name": val}
            out.append(cur)
            continue
        if cur is None or f is None:
            continue
        if f in ("channel",):
            cur["channel"] = _int(val)
        elif f == "signal":
            cur["signal"] = _int(val)
        elif f in ("rx", "tx"):
            cur[f] = _int(val)
        elif f == "bssid":
            mm = _MAC.search(val)
            cur["bssid"] = mm.group(1).lower() if mm else val
        elif f not in cur:
            cur[f] = val
    for it in out:
        it["band"] = band_of(it.get("channel"), it.get("band", ""))
        st = (it.get("state") or "").lower()
        it["connected"] = bool(it.get("ssid")) and ("disconn" not in st and "kesil" not in st)
    return out


def parse_networks(text: str) -> list[dict]:
    """`netsh wlan show networks mode=bssid` çıktısı → BSSID başına düz liste."""
    nets: list[dict] = []
    ssid = None
    auth = None
    cur: dict | None = None
    for line in text.splitlines():
        m = _KV.match(line)
        if not m:
            continue
        f = _field(m.group(1))
        val = m.group(2).strip()
        if f == "ssid_item":
            ssid, auth, cur = val, None, None
        elif f == "auth" and cur is None:
            auth = val
        elif f == "bssid_item":
            mm = _MAC.search(val)
            cur = {"ssid": ssid or "", "bssid": (mm.group(1).lower() if mm else val), "auth": auth}
            nets.append(cur)
        elif cur is not None:
            if f == "signal":
                cur["signal"] = _int(val)
            elif f == "channel":
                cur["channel"] = _int(val)
            elif f == "band":
                cur["band"] = val
            elif f == "radio":
                cur["radio"] = val
    for n in nets:
        n["band"] = band_of(n.get("channel"), n.get("band", ""))
        n.setdefault("signal", 0)
    return [n for n in nets if n.get("channel")]


def needs_location_permission(text: str) -> bool:
    t = text.lower()
    return "location" in t or "konum" in t


# 5 GHz 80 MHz blokları (ETSI / TR). DFS blokları radar algılarsa kanal değiştirir.
BLOCKS_5G = [
    {"primary": 36, "channels": [36, 40, 44, 48], "dfs": False},
    {"primary": 52, "channels": [52, 56, 60, 64], "dfs": True},
    {"primary": 100, "channels": [100, 104, 108, 112], "dfs": True},
    {"primary": 116, "channels": [116, 120, 124, 128], "dfs": True},
]


def recommend(networks: list[dict], own_ssid: str | None, own_bssids: set[str] | None = None) -> dict:
    """Komşu ağlara göre 2.4 GHz (1/6/11) ve 5 GHz (80 MHz blok) önerisi."""
    own_bssids = own_bssids or set()
    others = [n for n in networks
              if n["bssid"] not in own_bssids and not (own_ssid and n["ssid"] == own_ssid)]

    # 2.4 GHz: kanal merkezleri 5 kanal içinde örtüşür; sinyal gücüyle ağırlıklandır.
    load24 = {}
    for c in (1, 6, 11):
        score = 0.0
        for n in others:
            if n["band"] != "2.4":
                continue
            d = abs(n["channel"] - c)
            if d < 5:
                score += (n.get("signal") or 0) * (1 - d / 5)
        load24[c] = round(score, 1)
    best24 = min(load24, key=lambda c: (load24[c], c))

    load5 = []
    for b in BLOCKS_5G:
        score = sum((n.get("signal") or 0) for n in others
                    if n["band"] == "5" and n["channel"] in b["channels"])
        load5.append({**b, "load": score})
    non_dfs = load5[0]
    best5 = non_dfs
    # DFS bloğunu yalnızca 36-48 belirgin şekilde doluysa öner.
    cand = min(load5[1:], key=lambda b: b["load"])
    if non_dfs["load"] > 150 and cand["load"] < non_dfs["load"] / 2:
        best5 = cand

    counts = {"2.4": {}, "5": {}}
    for n in others:
        if n["band"] in counts:
            counts[n["band"]][n["channel"]] = counts[n["band"]].get(n["channel"], 0) + 1
    return {
        "load_24": load24,
        "best_24": best24,
        "load_5": load5,
        "best_5": {"channel": best5["primary"], "dfs": best5["dfs"], "width": 80},
        "neighbor_counts": counts,
        "neighbors": len(others),
    }
