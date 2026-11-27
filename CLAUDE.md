# Claude Code Talimatları

## 1. Genel kurallar (her işte geçerli, promptta yazmasa bile)
1. Token kullanımını en aza indir. Promptta gereksiz ifade varsa önce düzeltilmiş halini öner.
2. İşi adım adım yap.
3. İşe başlamadan önce tüm adımları planla ve gereken bütün soruları tek seferde, en başta sor. İş başladıktan sonra yeni soru sorma; zorunluysa tek kısa soru sor.
4. Fazlar arasında geçerken 1 dakika bekle, sonra onay beklemeden devam et.
5. 5 saatlik kullanım limiti dolarsa, limit sıfırlandığında kaldığın adımdan devam et.

## 2. Sürüm yayınlama
Ne zaman: Uygulamanın yeni sürümü hazır olduğunda veya APK istendiğinde/üretildiğinde.
Nasıl: Ayrıca söylenmesini bekleme, izin sorma, adımlar arasında bekleme yapma (1. bölümdeki 1 dk bekleme burada uygulanmaz).

### Tüm uygulamalar
1. Değişikliklerin GitHub'a commit/push edildiğini kontrol et; edilmemişse önce commit/push et.
2. Repodaki mevcut sürüm numarasını oku (package.json, build.gradle, version dosyası vb.).
3. Sürümü artır:
   - Hata düzeltme → son rakam (1.2.3 → 1.2.4)
   - Yeni özellik → ortadaki rakam, son rakam sıfırlanır (1.2.3 → 1.3.0)
   - Emin değilsen tek kısa soru sor.
4. Yeni sürüm numarasını repodaki sürüm dosyasına yaz.
5. Adlandırma her zaman: `UygulamaAdı_vX.Y.Z`

### Web uygulamaları
6. Sürüm numarasını uygulama ekranındaki başlıkta göster (ör. "Emsal Hesabı v1.3.0").
7. GitHub'da `UygulamaAdı_vX.Y.Z` adıyla release/tag aç.
8. Drive'a hiçbir kopya veya yedek koyma; web uygulamaları yalnızca GitHub'da durur.

### APK uygulamaları
6. APK'yı `UygulamaAdı_vX.Y.Z.apk` adıyla üret.
7. Google Drive'daki "Claude Apk" klasörüne yükle.
8. Yükleme başarılıysa: aynı uygulamanın klasördeki eski sürüm dosyasını çöpe at.
   - Yalnızca aynı uygulama adıyla başlayan dosyaya dokun; başka uygulamaların dosyalarına dokunma.
   - "Silme" = Drive çöp kutusuna atma, kalıcı silme yok.
9. Yükleme başarısızsa: eski sürümü silme, durumu bildir.
10. Klasörde o uygulamadan yalnızca yeni sürümün kaldığını doğrula.

### Bildirim
- İş bitince tek cümleyle bildir: uygulama adı, eski sürüm → yeni sürüm, kayıt yeri (web: GitHub, APK: Drive "Claude Apk").

## 3. Yeni repo
1. "Yeni repo aç" talimatı geldiğinde repoyu bu dosyayı (CLAUDE.md) içerecek şekilde oluştur.
2. Bu kural yalnızca yeni açılan repolar için geçerlidir; mevcut repolara CLAUDE.md ekleme.

## 4. Proje mimarisi (EX20v Ağ Kontrol Merkezi)
- `index.html`: tek dosya PWA, iPhone öncelikli. Derleme ve çerçeve yok; CSS ve simge seti (Lucide, `<symbol>`) dosyaya gömülü. Chart.js ve QR kitaplığı yalnızca gerektiğinde CDN'den yüklenir.
  - Gezinme: altta 5 sekme (Özet, Test, Cihazlar, Modem, Ayarlar) + alt sayfalar (`kanal`, `baglan`) + alttan açılan paneller (`sheet`, `ask`).
  - Dil: sade Türkçe; teknik terimler yalnızca "Teknik ayrıntılar" altında.
- `agent/server.py`: FastAPI yerel ajan (0.0.0.0:8080). API + arayüz dosyalarını (beyaz liste) sunar.
  - `netutil.py` (ping, ARP taraması, DNS kıyası, OUI), `netsh_parser.py` (TR/EN netsh ayrıştırma + kanal önerisi), `router.py` (tplinkrouterc6u ile EX20v kontrolü).
  - `credentials.py`: markaya göre fabrika varsayılanı kullanıcı adı/parola kütüphanesi + marka algılama (yalnızca kullanıcının kendi modemine giriş içindir).
  - Veriler `agent/data/` (SQLite, config.json, manuf önbelleği) — git'e girmez.
- Hibrit mod: arayüz açılışta `/api/health`'e 1.5 sn istek atar; ajan varsa tam mod, yoksa tarayıcı modu.
- Ağ Doktoru / Tek Tuşla Optimize (`optimize` alt sayfası): `analyze()` sorunlarından sıralı bir düzeltme planı kurar. Otomatik (modem API'si destekliyorsa, ör. kapalı 5 GHz'i açma) + rehberli (kanal/DNS/QoS — modem sayfasını açar). EX20v'de tplinkrouterc6u yalnızca bant aç/kapat ve reboot destekler; kanal/DNS/QoS körlemesine yazılmaz.
- Varsayılan şifreyle giriş: `/api/router/detect` (markayı HTTP ile tahmin) + `/api/router/try-defaults` (sıralı varsayılanları dener, çalışanı bildirir, varsayılan parola güvenlik uyarısıyla). Parolayı kaydetmez; kullanıcı onayıyla kaydedilir. Deneme sayısı modemi kilitlememek için sınırlı.
- Telefon eşleştirme: bilgisayardaki sayfa `http://PC-IP:8080/#k=ANAHTAR` adresini QR olarak gösterir. HTTPS (Pages) sayfası LAN'daki HTTP ajana bağlanamaz; telefon bu adresi açar. Ajan, kendi sunduğu sayfada Ana Ekran adını "Ev Ağım" yapar ve manifest'ten `start_url`'i çıkarır.
- Güvenlik: CORS yalnızca `https://celal84.github.io` + localhost; başka kökenden POST reddedilir; modemi değiştiren işlemler localhost dışından `X-Agent-Key` ister (arayüz 401'de anahtarı sorar).
- Ölçüm: ping = tarayıcı ağ zamanlaması (Resource Timing) − Cloudflare `server-timing` içindeki **tüm** `dur` değerleri. Yöntem değişirse `MV` artırılır; eski kayıtlar özet ve karşılaştırmada kullanılmaz.
- Modem menü yolları `index.html` → `MENU` nesnesinde tek yerde ([Türkçe, İngilizce] çiftleri).
- Sürüm 4 yerde birlikte güncellenir: `VERSION`, `index.html`, `agent/server.py`, `sw.js`. Tag adı: `EX20v_Ag_Kontrol_Merkezi_vX.Y.Z`.
- Yayın: `main`'e gelen değişiklik `.github/workflows/pages.yml` ile GitHub Pages'e çıkar.
- Test: `python -m unittest discover -s agent/tests`; arayüz için Playwright ile iPhone boyutunda ekran kontrolü.
