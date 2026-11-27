# EX20v Ağ Kontrol Merkezi

TP-Link **EX20v (AX1800)** modemli ev ağınızı **iPhone'dan** yönetmek için web uygulaması.
Tamamen Türkçe, kurulum gerektirmez; Ana Ekrana eklenince uygulama gibi açılır.

**Adres:** https://celal84.github.io/WIFI-Komuta/

## Neler yapar?

| | İnternet adresi (her yerde) | Evde, bilgisayarla eşleştirilince |
|---|:-:|:-:|
| Hız, tepki süresi ve "yoğunlukta takılma" testi | ✅ | ✅ |
| 0–100 ağ sağlık puanı ve sade Türkçe öneriler | ✅ | ✅ |
| Modem ayar rehberi (kanal, DNS, QoS hesaplayıcı) | ✅ | ✅ |
| Test geçmişi ve öncesi/sonrası karşılaştırma | ✅ | ✅ |
| Bağlı cihazlar, bilinmeyen cihaz uyarısı | — | ✅ |
| **Modem kontrolü:** Wi-Fi ve misafir ağını aç/kapat, yeniden başlat | — | ✅ |
| Wi-Fi kanal analizi (en boş kanal) | — | ✅ |

## iPhone'da kullanım

### 1. Yalnızca hız testi (hemen)
1. Safari'de https://celal84.github.io/WIFI-Komuta/ adresini açın.
2. **Paylaş → Ana Ekrana Ekle** deyin.

### 2. Tam kontrol (evdeyken)
Tarayıcılar, güvenlik gereği bir internet sitesinin evdeki modeme doğrudan erişmesine izin vermez.
Bu yüzden evdeki Windows bilgisayarda küçük bir yardımcı program çalışır ve telefon onun üzerinden bağlanır.

1. Bilgisayara [Python 3.11+](https://www.python.org/downloads/) kurun (kurulumda "Add python.exe to PATH" işaretli olsun).
2. Bu repoyu indirin (**Code → Download ZIP**), klasördeki **`baslat.bat`** dosyasına çift tıklayın.
   İlk açılışta gerekenler kendiliğinden kurulur ve tarayıcıda uygulama açılır.
   Windows Güvenlik Duvarı sorarsa **Özel ağlar** için izin verin.
3. Bilgisayarda **Özet → iPhone'da Kullan** bölümündeki **QR kodu** iPhone kamerasıyla okutun.
4. Telefonda açılan sayfada **Paylaş → Ana Ekrana Ekle** deyin ("Ev Ağım" simgesi oluşur).
5. **Modem** sekmesinde modem parolanızı bir kez girin.

> `baslat.bat` penceresi açık kaldığı sürece telefon tam kontrol sağlar. Pencere kapalıyken "Ev Ağım" simgesi açılmaz;
> hız testi için internet adresini kullanabilirsiniz.

## Sık sorulanlar

**QR okutamıyorum.** `baslat.bat` penceresinde yazan adresi (ör. `http://192.168.1.20:8080`) Safari'ye yazın.
Modem işlemlerinde bir kez sorulan 6 haneli eşleştirme anahtarı da aynı pencerede yazar.

**"Ev Ağım" simgesi açılmıyor.** Bilgisayar ve `baslat.bat` açık mı? Telefon evdeki Wi-Fi'da mı?
Bilgisayarın adresi değiştiyse QR'ı yeniden okutun.

**Modeme bağlanamıyor.** Kullanıcı adı EX20v'de çoğunlukla `user`'dır (Modem → Gelişmiş).
TP-Link ID ile değil, modem arayüzünün yerel parolasıyla giriş yapılır.
Modem arayüzü başka bir tarayıcıda açıksa önce oradan çıkış yapın (modem tek oturuma izin verir).

**Cihaz engelleme otomatik değil.** EX20v yazılımı bunu dışarıdan desteklemiyor; uygulama MAC adresini kopyalar ve
modemde izlenecek adımları gösterir.

**Kanal analizi çalışmıyor.** Bilgisayar Wi-Fi ile bağlı olmalı. Windows 11'de
**Ayarlar → Gizlilik ve güvenlik → Konum** altında "Konum hizmetleri" ve
"Masaüstü uygulamalarının konumunuza erişmesine izin ver" açık olmalı.

**Menü adları modemimde farklı.** Menü yolları `index.html` içindeki `MENU` nesnesindedir; yalnızca orayı düzeltin.

**Verilerim nerede?** Test geçmişi telefonda (veya eşleştirilmişse evdeki bilgisayarda) saklanır.
Modem parolası yalnızca evdeki bilgisayarda `agent/data/config.json` dosyasındadır. Hiçbir veri dışarı gönderilmez;
hız testi yalnızca Cloudflare'in ölçüm sunucusuyla veri alışverişi yapar.

## Geliştirme
```bash
pip install -r agent/requirements.txt
python agent/server.py                         # http://localhost:8080 , API belgesi: /api/docs
python -m unittest discover -s agent/tests     # netsh / arp / ping ayrıştırıcı testleri
```
- `index.html` tek dosyadır; derleme ve harici çerçeve yoktur (grafik ve QR kitaplıkları gerektiğinde CDN'den yüklenir).
- `main` dalına gelen her değişiklik GitHub Pages'e kendiliğinden yayınlanır (`.github/workflows/pages.yml`).
- Sürüm numarası dört yerde birlikte güncellenir: `VERSION`, `index.html`, `agent/server.py`, `sw.js`.
- Simgeler: [Lucide](https://lucide.dev) (ISC lisansı).
