"""Modem markasına göre fabrika çıkışı (varsayılan) kullanıcı adı/parola kütüphanesi.

Buradaki bilgiler herkese açık kaynaklardan derlenmiştir (modem etiketleri, üretici
kılavuzları) ve YALNIZCA kullanıcının KENDİ modemine girişi kolaylaştırmak içindir.
Bir varsayılan parola hâlâ çalışıyorsa bu bir güvenlik zafiyetidir; arayüz bunu
kullanıcıya bildirir ve değiştirmesini önerir.

Her girişin parolası denenme sırasına göre dizilidir (en olası ilk).
Türkiye'de yaygın internet sağlayıcısı modemleri öncelikli tutulmuştur.
"""
from __future__ import annotations

# (kullanıcı adı, parola, kısa açıklama)
Cred = tuple  # (str, str, str)

# Marka tanımları. host_hints: giriş sayfasının gövde/başlık/başlıklarında aranan
# küçük harfli ipuçları (marka algılama için). creds: denenecek varsayılanlar.
BRANDS: list[dict] = [
    {
        "brand": "TP-Link",
        "hints": ["tp-link", "tplink", "tl-wr", "archer", "ex20", "/webpages/"],
        "creds": [
            ("admin", "admin", "TP-Link klasik"),
            ("user", "user", "TP-Link EX serisi"),
            ("admin", "", "TP-Link (boş parola)"),
        ],
    },
    {
        "brand": "Türk Telekom",
        "hints": ["turk telekom", "türk telekom", "ttnet", "ttgnet", "home gateway"],
        "creds": [
            ("admin", "admin", "Türk Telekom yaygın"),
            ("admin", "ttnet", "TTNET"),
            ("admin", "password", "Türk Telekom"),
            ("ttnet", "ttnet", "TTNET"),
        ],
    },
    {
        "brand": "Turkcell Superonline",
        "hints": ["superonline", "turkcell", "veranet"],
        "creds": [
            ("admin", "admin", "Superonline yaygın"),
            ("admin", "superonline", "Superonline"),
            ("superonline", "superonline", "Superonline"),
        ],
    },
    {
        "brand": "Vodafone",
        "hints": ["vodafone", "vodafonenet"],
        "creds": [
            ("vodafone", "vodafone", "Vodafone"),
            ("admin", "vodafone", "Vodafone"),
            ("admin", "admin", "Vodafone"),
        ],
    },
    {
        "brand": "Zyxel",
        "hints": ["zyxel"],
        "creds": [("admin", "1234", "Zyxel klasik"), ("admin", "admin", "Zyxel")],
    },
    {
        "brand": "Huawei",
        "hints": ["huawei", "echolife", "hg8"],
        "creds": [("admin", "admin", "Huawei"), ("root", "admin", "Huawei ONT"), ("telecomadmin", "admintelecom", "Huawei ONT yönetici")],
    },
    {
        "brand": "ZTE",
        "hints": ["zte", "zxhn"],
        "creds": [("admin", "admin", "ZTE"), ("user", "user", "ZTE")],
    },
    {
        "brand": "AirTies",
        "hints": ["airties", "air "],
        "creds": [("admin", "admin", "AirTies"), ("admin", "ttnet", "AirTies TTNET")],
    },
    {
        "brand": "Asus",
        "hints": ["asus", "rt-ac", "rt-ax"],
        "creds": [("admin", "admin", "Asus")],
    },
    {
        "brand": "Netgear",
        "hints": ["netgear", "nighthawk", "orbi"],
        "creds": [("admin", "password", "Netgear"), ("admin", "1234", "Netgear")],
    },
    {
        "brand": "D-Link",
        "hints": ["d-link", "dlink", "dir-"],
        "creds": [("admin", "", "D-Link (boş)"), ("admin", "admin", "D-Link"), ("user", "", "D-Link")],
    },
    {
        "brand": "Tenda",
        "hints": ["tenda"],
        "creds": [("admin", "admin", "Tenda")],
    },
    {
        "brand": "Mercusys",
        "hints": ["mercusys"],
        "creds": [("admin", "admin", "Mercusys")],
    },
]

# Marka belirlenemezse denenecek genel varsayılanlar (sıra önemlidir).
GENERIC: list = [
    ("admin", "admin", "Genel"),
    ("admin", "password", "Genel"),
    ("admin", "", "Genel (boş parola)"),
    ("user", "user", "Genel"),
    ("admin", "1234", "Genel"),
    ("root", "root", "Genel"),
    ("admin", "0000", "Genel"),
]


def detect_brand(text: str, headers: str = "") -> str | None:
    """Giriş sayfasının metni/başlıklarından marka tahmin eder. Bulamazsa None."""
    hay = f"{text} {headers}".lower()
    best, best_len = None, 0
    for b in BRANDS:
        for h in b["hints"]:
            if h in hay and len(h) > best_len:
                best, best_len = b["brand"], len(h)
    return best


def candidates(brand: str | None = None, extra: list | None = None) -> list:
    """Denenecek (kullanıcı adı, parola, açıklama) listesi.

    Önce verilen marka, sonra Türkiye'de yaygın sağlayıcılar, sonra genel liste.
    Aynı (kullanıcı, parola) çifti yinelenmez. `extra`: kullanıcının eklediği çiftler.
    """
    out: list = []
    seen: set = set()

    def add(items):
        for c in items:
            u, p = c[0], c[1]
            note = c[2] if len(c) > 2 else ""
            if (u, p) not in seen:
                seen.add((u, p))
                out.append((u, p, note))

    if extra:
        add(extra)
    if brand:
        for b in BRANDS:
            if b["brand"] == brand:
                add(b["creds"])
    # Türkiye'de yaygın sağlayıcı modemleri (marka bilinmese de sık tutar)
    for name in ("TP-Link", "Türk Telekom", "Turkcell Superonline", "Vodafone"):
        for b in BRANDS:
            if b["brand"] == name:
                add(b["creds"])
    add(GENERIC)
    return out


def is_default(username: str, password: str) -> bool:
    """Verilen çift bilinen bir fabrika varsayılanı mı? (güvenlik uyarısı için)"""
    for src in [GENERIC] + [b["creds"] for b in BRANDS]:
        for c in src:
            if c[0] == username and c[1] == password:
                return True
    return False
