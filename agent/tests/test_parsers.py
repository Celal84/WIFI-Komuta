"""Ayrıştırıcı testleri: python -m unittest discover -s agent/tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import netsh_parser as p  # noqa: E402
import netutil as n  # noqa: E402

IF_TR = """
Sistemde 1 arabirim var:

    Ad                     : Wi-Fi
    Açıklama               : Intel(R) Wi-Fi 6 AX201 160MHz
    Fiziksel adres         : aa:bb:cc:dd:ee:ff
    Durum                  : bağlandı
    SSID                   : EvAgi
    AP BSSID               : 11:22:33:44:55:66
    Bant                   : 2,4 GHz
    Kanal                  : 6
    Radyo türü             : 802.11ax
    Kimlik doğrulaması     : WPA2-Kişisel
    Alma hızı (Mbps)       : 286,8
    İletim hızı (Mbps)     : 286,8
    Sinyal                 : %78
    Profil                 : EvAgi
"""
IF_EN = """
There is 1 interface on the system:

    Name                   : Wi-Fi
    Description            : Intel(R) Wi-Fi 6 AX201 160MHz
    State                  : connected
    SSID                   : Home
    AP BSSID               : 11:22:33:44:55:77
    Radio type             : 802.11ax
    Channel                : 36
    Receive rate (Mbps)    : 1201
    Transmit rate (Mbps)   : 1201
    Signal                 : 92%
"""
NET_TR = """
Arabirim adı : Wi-Fi
Şu anda 3 ağ görünür.

SSID 1 : EvAgi
    Ağ türü                 : Altyapı
    Kimlik doğrulaması      : WPA2-Kişisel
    Şifreleme               : CCMP
    BSSID 1                 : 11:22:33:44:55:66
         Sinyal             : %78
         Radyo türü         : 802.11ax
         Bant               : 2,4 GHz
         Kanal              : 6
         Kanal Kullanımı    : 40 (15 %)
    BSSID 2                 : 11:22:33:44:55:67
         Sinyal             : %70
         Bant               : 5 GHz
         Kanal              : 36

SSID 2 : Komsu
    Kimlik doğrulaması      : WPA2-Kişisel
    BSSID 1                 : 22:22:33:44:55:66
         Sinyal             : %90
         Kanal              : 1

SSID 3 : Komsu5
    BSSID 1                 : 33:22:33:44:55:66
         Signal             : 80%
         Channel            : 40
         Channel Utilization: 12 (4 %)
"""
ARP_WIN = """
Arabirim: 192.168.1.20 --- 0xb
  İnternet Adresi       Fiziksel Adres        Tür
  192.168.1.1           a4-2b-b0-11-22-33     dinamik
  192.168.1.35          da-a1-19-00-11-22     dinamik
  192.168.1.255         ff-ff-ff-ff-ff-ff     statik
  224.0.0.22            01-00-5e-00-00-16     statik
"""
PING_TR = """
192.168.1.1 yanıtı: bayt=32 süre=2ms TTL=64
192.168.1.1 yanıtı: bayt=32 süre<1ms TTL=64
İstek zaman aşımına uğradı.
192.168.1.1 yanıtı: bayt=32 süre=12ms TTL=64
"""


class T(unittest.TestCase):
    def test_if_tr(self):
        i = p.parse_interfaces(IF_TR)[0]
        self.assertEqual((i["ssid"], i["channel"], i["signal"], i["band"], i["rx"]), ("EvAgi", 6, 78, "2.4", 286))
        self.assertTrue(i["connected"])

    def test_if_en(self):
        i = p.parse_interfaces(IF_EN)[0]
        self.assertEqual((i["ssid"], i["channel"], i["band"], i["signal"]), ("Home", 36, "5", 92))

    def test_networks(self):
        nets = p.parse_networks(NET_TR)
        self.assertEqual(len(nets), 4)
        self.assertEqual([x["channel"] for x in nets], [6, 36, 1, 40])
        self.assertEqual(nets[3]["band"], "5")
        rec = p.recommend(nets, "EvAgi")
        self.assertIn(rec["best_24"], (6, 11))
        self.assertGreater(rec["load_24"][1], 0)
        self.assertEqual(rec["best_5"]["channel"], 36)
        self.assertEqual(rec["neighbors"], 2)

    def test_arp(self):
        t = n.parse_arp(ARP_WIN)
        self.assertEqual(t, {"192.168.1.1": "a4:2b:b0:11:22:33", "192.168.1.35": "da:a1:19:00:11:22"})
        self.assertTrue(n.is_random_mac("da:a1:19:00:11:22"))
        self.assertFalse(n.is_random_mac("a4:2b:b0:11:22:33"))

    def test_ping(self):
        t = n.parse_ping(PING_TR)
        self.assertEqual(t, [2.0, 1.0, 12.0])
        s = n.summarize(t, 4)
        self.assertEqual(s["loss"], 25.0)


if __name__ == "__main__":
    unittest.main()
