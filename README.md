# EX20v Ağ Kontrol Merkezi

TP-Link **EX20v (AX1800, 192.168.1.1)** modemli ev ağı için hibrit kontrol paneli (PWA).
Telefondan da bilgisayardan da çalışır; derleme veya Node.js gerekmez.

| Özellik | Tarayıcı modu (GitHub Pages) | Yerel ajan modu (`baslat.bat`) |
|---|:-:|:-:|
| Hız, ping, jitter, bufferbloat testi (Cloudflare) | ✅ | ✅ |
| Ağ sağlık puanı, EX20v çözüm kartları, QoS hesaplayıcı | ✅ | ✅ |
| Ölçüm geçmişi ve grafik | ✅ (tarayıcıda) | ✅ (SQLite) |
| EX20v'ye yerel ping, paket kaybı, DNS kıyası | — | ✅ |
| Bağlı cihazlar, isim/kategori, bilinmeyen cihaz uyarısı | — | ✅ |
| Wi-Fi kanal analizi ve en boş kanal önerisi | — | ✅ (Windows + Wi-Fi kartı) |
| **Modemi doğrudan kontrol**: durum, Wi-Fi/misafir ağı aç-kapa, yeniden başlatma | — | ✅ |

## 1. GitHub Pages'i açma (bir kez)
1. GitHub'da repo → **Settings → Pages**.
2. *Source*: **Deploy from a branch**, *Branch*: `main` / `(root)` → **Save**.
3. Birkaç dakika sonra adres: `https://celal84.github.io/WIFI-Komuta/`
4. Telefonda açıp **Ana Ekrana Ekle** deyin (PWA).

> Ücretsiz GitHub planında Pages yalnızca **herkese açık** repolarda çalışır.

## 2. Yerel ajanı çalıştırma (Windows)
1. [Python 3.11+](https://www.python.org/downloads/) kurun ("Add python.exe to PATH" işaretli).
2. Repoyu indirin (Code → Download ZIP) ve klasördeki **`baslat.bat`** dosyasına çift tıklayın.
   İlk açılışta gerekli paketler otomatik kurulur, tarayıcı `http://localhost:8080` ile açılır.
3. Windows Güvenlik Duvarı sorarsa **Özel ağlar** için izin verin.
4. Pencerede yazan şu iki bilgiyi not edin:
   - **Telefondan:** `http://<PC-IP>:8080`
   - **Ajan anahtarı:** 6 haneli sayı (telefondan modem işlemi yapmak için Ayarlar'a girilir)

### Telefondan tam mod
GitHub Pages sayfası HTTPS'tir; tarayıcılar HTTPS sayfanın evdeki HTTP ajana bağlanmasını engeller.
Bu yüzden telefonda tam mod için **`http://<PC-IP>:8080`** adresini açın (aynı arayüzü ajan sunar).
Aynı bilgisayardaki tarayıcıda GitHub Pages adresi ajanı otomatik bulur
(Chrome "yerel ağdaki cihazlara erişim" izni sorarsa **İzin ver**).

### Modem bağlantısı (tam kontrol)
**Modem** sekmesinde modemin yerel yönetici parolasını girin. Kullanıcı adı EX serisinde genelde **`user`**'dır.
Ajan, açık kaynak [tplinkrouterc6u](https://github.com/AlexandrErohin/TP-Link-Archer-C6U) kütüphanesiyle
EX20v arayüzüne giriş yapar. Parola yalnızca bu bilgisayarda `agent/data/config.json` içinde saklanır (git'e girmez).
- Modem web arayüzü tarayıcıda açıkken ajan giriş yapamaz (modem tek oturuma izin verir).
- EX20v firmware'i otomatik kara listeyi desteklemiyorsa uygulama MAC'i kopyalar ve menü yolunu gösterir.

### Wi-Fi kanal analizi
- Bilgisayar **Wi-Fi ile** bağlı olmalı (kablolu PC'de komşu ağlar görülemez).
- Windows 11'de **Ayarlar → Gizlilik ve güvenlik → Konum**: "Konum hizmetleri" ve
  "Masaüstü uygulamalarının konumunuza erişmesine izin ver" açık olmalı (aksi halde `netsh` ağ listesi vermez).

## Menü yolları
Uygulamadaki EX20v menü yolları `index.html` içindeki `MENU` nesnesindedir.
Sağlayıcı firmware'inde farklıysa yalnızca orayı düzeltin.

## Geliştirme
```bash
pip install -r agent/requirements.txt
python agent/server.py                         # http://localhost:8080 , API belgesi: /api/docs
python -m unittest discover -s agent/tests     # netsh / arp / ping ayrıştırıcı testleri
```
Sürüm numarası: `VERSION`, `index.html` (`VERSION`), `agent/server.py` (`VERSION`), `sw.js` (`CACHE`).
