# 🎮 ParsLinux Nvidia Installer

[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](LICENSE)
[![ParsLinux](https://img.shields.io/badge/ParsLinux-Ecosystem-orange.svg)](https://parslinux.org)
[![Python 3](https://img.shields.io/badge/Python-3.8+-green.svg)](https://www.python.org/)
[![GTK 4](https://img.shields.io/badge/GUI-GTK%204-blue.svg)](https://www.gtk.org/)
[![Version](https://img.shields.io/badge/Version-1.2.0-brightgreen.svg)](docs/VERSION.md)

**ParsLinux Nvidia Installer**, ParsLinux işletim sisteminde resmi NVIDIA grafik sürücülerini tek tıkla kurmayı, güncellemeyi, donanım telemetrisini canlı izlemeyi, fan ve güç limitlerini ayarlamayı, oyun hızlandırmayı ve yapay zeka/CUDA ortamını yapılandırmayı sağlayan modern bir grafiksel sistem merkezidir.

Pardus projesinin `pardus-nvidia-installer` aracından forklanarak ParsLinux mimarisine, çoklu dağıtım paketleme sistemine ve ParsLinux görsel kimliğine uyarlanmış; üzerine telemetri, güç yönetimi, oyun hızlandırıcı ve sistem tepsisi katmanları eklenmiştir.

<p align="center">
  <img src="images/screenshot.png" alt="ParsLinux Nvidia Installer Hero Screenshot" width="750" />
</p>

---

## 📸 Ekran Görüntüleri

| 🎮 Sürücüler & Otomatik Tavsiye | 📊 Donanım İzleme, Güç & Fan |
|:---:|:---:|
| <img src="images/screenshot_drivers.png" width="380" alt="Sürücü Yönetimi" /> | <img src="images/screenshot_monitor.png" width="380" alt="Donanım İzleme & Güç" /> |
| **Kart tespiti, önerilen sürücü & tek tık kurulum** | **Canlı sensörler, PRIME profilleri, Fan/Güç & OC** |

| 🕹️ Oyun Hızlandırıcı & HUD | 🧠 Yapay Zeka & CUDA Ortamı |
|:---:|:---:|
| <img src="images/screenshot_gaming.png" width="380" alt="Oyun Hızlandırıcı" /> | <img src="images/screenshot_ai.png" width="380" alt="Yapay Zeka & CUDA" /> |
| **PRIME Offload, Steam/Lutris optimizasyonu & MangoHud** | **CUDA Toolkit, cuDNN ve TensorRT entegrasyonu** |

---

## 🚀 Temel Özellikler

- 🔍 **Akıllı Donanım Tespiti:** Sistemdeki PCI veriyolunu tarayarak NVIDIA kartlarını otomatik algılar.
- 🎯 **Donanıma Özel Sürücü Önerisi:** Kartınızın mimarisine (`RTX`, `GTX`, `Tesla 470`, `Nouveau`) en uygun sürücüyü filtreleyerek sunar.
- 📊 **Canlı Donanım İzleme & Sensörler:** Gerçek zamanlı GPU sıcaklığı (renk kodlu), fan devri, VRAM kullanımı (GB ve çubuk) ve anlık güç tüketimi (`Watt`).
- ⚡ **PRIME Güç Profili Seçici:** Melez (Optimus/hybrid) dizüstü bilgisayarlarda 3 profil:
  - 🍃 **Tasarruf (Entegre):** NVIDIA GPU'yu uyutup batarya ömrünü maksimuma çıkarır.
  - ⚡ **Hibrit (İsteğe Bağlı):** Masaüstü entegre kartta çalışır, oyunlar NVIDIA ile başlar.
  - 🚀 **Performans (NVIDIA):** Sürekli harici GPU devrededir, harici ekranlar aktiftir.
- ⚙️ **Özel Fan Eğrisi & Güç Sınırı (Power Limit):** Fan devrini (%20-%100) ve kartın maksimum güç sınırını (TDP) kaydırıcılarla manuel ayarlama.
- 🕹️ **Oyun Hızlandırıcı & PRIME Offload:** Steam, Lutris, Heroic ve Bottles oyunlarını otomatik olarak yüksek performanslı NVIDIA GPU ve Vulkan/DXVK katmanıyla açar (`/etc/environment.d`).
- 🧠 **Yapay Zeka ve Geliştirici Kütüphaneleri:** Tek tıkla **CUDA Toolkit** (`nvcc`), **cuDNN** ve **TensorRT** kurulum sihirbazı.
- 🖥️ **Sistem Tepsisi (AppIndicator / Tray):** Masaüstü üst barında canlı sıcaklık ve profil göstergesi (`45°C • Hibrit`) ve sağ tık hızlı erişim menüsü (`--tray` / `-t`).
- 🛡️ **Güvenli Çekirdek Filtresi:** Birincil ekran bağdaştırıcısını (`boot_vga=1`) asla kaldırmaz; siyah ekran riskini önler.
- 🖥️ **Entegre VTE Terminali:** Kurulum ve kaldırma adımlarını gerçek zamanlı terminal günlüğüyle takip etme imkanı.
- 🧪 **Geliştirici & Sanal Makine Simülasyonu:** NVIDIA kartı bulunmayan cihazlarda dahi `--debug` moduyla tam arayüz testi.
- 📦 **Çift Paketleme Desteği:** Hem Debian tabanlı sistemler için `.deb` hem de Arch Linux / CachyOS için `.pkg.tar.zst` paketleme.

---

## 🛠️ Sistem Gereksinimleri

| Bileşen | Paket Adı (Debian / ParsLinux) | Paket Adı (Arch Linux / CachyOS) |
|---|---|---|
| **Python** | `python3` (3.8+) | `python` |
| **GObject Introspection** | `python3-gi`, `gir1.2-gtk-4.0` | `python-gobject`, `gtk4` |
| **Terminal Bileşeni** | `gir1.2-vte-2.91` | `vte3` |
| **Sistem Tepsisi** | `gir1.2-ayatanaappindicator3-0.1` | `libayatana-appindicator` |
| **Yetkilendirme (Polkit)** | `gir1.2-polkit-1.0`, `policykit-1` | `polkit` |
| **Donanım Tanıma** | `pciutils` | `hwdata` |
| **GPG Doğrulama** | `gnupg` | `gnupg` |

---

## 💻 Kullanım ve Hızlı Başlangıç

### Geliştirici / Yerel Çalıştırma
```bash
# Donanım tespiti yaparak başlatma (kart yoksa otomatik simülasyon)
./run.sh

# Simüle edilmiş RTX 4070 Ti kartı ile demo modu
./run.sh --debug

# Sistem tepsisi göstergesini başlatma
./parslinux-nvidia-installer --tray

# Master kontrol paneli
./manage.sh
```

### Sistem Kurulumu
```bash
# Otomatik bağımlılık kontrolü ve sisteme kurulum
./install.sh

# Sistemden temiz kaldırma
./uninstall.sh
```

### Paket Derleme (.deb ve .pkg.tar.zst)
```bash
# Otomatik tespit ve derleme
./package.sh

# Sadece Debian paketi (.deb) derleme
./package.sh --deb

# Sadece Arch paketi (.pkg.tar.zst) derleme
./package.sh --arch
```

### Testleri Çalıştırma
```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
# veya
./manage.sh test
```

---

## 📁 Proje Dizin Yapısı

```
parslinux-nvidia-installer/
├── parslinux-nvidia-installer      # Ana ikili başlatıcı (CLI / GUI)
├── pardus-nvidia-installer         # Geriye dönük uyumluluk sembolik bağı
├── org.parslinux.nvidia-installer.desktop # XDG masaüstü kısayolu
├── org.parslinux.pkexec.parslinux-nvidia-installer.policy # Polkit güvenlik politikası
├── pni-disable-gpu.service         # Melez kart açılış systemd servisi
├── pni-disable-gpu.sh              # Melez kart PCI yönetim betiği
├── nvidia.pub                      # Resmi NVIDIA GPG imza anahtarları
├── setup.py                        # Python kurulum betiği
├── meson.build                     # Meson derleme tanımı
├── PKGBUILD / .SRCINFO             # Arch Linux / CachyOS paket tanımları
├── debian/                         # Debian paketleme ve betikleri
├── docs/                           # Kapsamlı standart dokümantasyon seti
├── src/
│   ├── Main.py                     # Gtk.Application giriş noktası ve CLI ayrıştırıcı
│   ├── MainWindow.py               # 4 sekmeli ana pencere denetleyicisi
│   ├── monitor.py                  # Canlı GPU telemetri, sensör, PRIME ve AI tespit motoru
│   ├── tray.py                     # Sistem tepsisi (AppIndicator) durum göstergesi
│   ├── nvidia.py                   # PCI donanım tespiti ve sürücü eşleme motoru
│   └── package.py                  # PolicyKit root yetkili paket ve donanım yürütücüsü
└── tests/                          # 20/20 birim test takımı
```

---

## 🤝 Katkıda Bulunma ve Lisans

Katkıda bulunma yönergeleri için [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) belgesini inceleyebilirsiniz.
Bu proje **GNU General Public License v3.0 (GPL-3.0-or-later)** ile lisanslanmıştır.
Tüm hakları ParsLinux Topluluğu ve katkıcılarına aittir.
