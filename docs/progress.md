# 📊 İlerleme ve Yol Haritası (`progress.md`)

## 📌 Tamamlanan Görevler (v1.0.0, v1.1.0 & v1.2.0)
- [x] Kaynak kodun `pardus-nvidia-installer` deposundan incelenmesi ve çatallanması.
- [x] Tüm marka ve meta verilerin `parslinux-nvidia-installer` olarak dönüştürülmesi.
- [x] TÜBİTAK/BİLGEM ve Pardus kalıntılarının kaynak koddan temizlenmesi.
- [x] Yüksek çözünürlüklü ParsLinux kurumsal vektörel SVG ikonlarının üretilmesi (`images/` ve `data/assets/`).
- [x] Eski 765 KB'lık raster kart görselinin modern hafif vektörle değiştirilmesi.
- [x] Gtk.Application mimarisinin `NON_UNIQUE` bayrağı ve çoklu argüman desteğiyle modernize edilmesi.
- [x] Donanım olmayan makinelerde sorunsuz test için donanım simülatörü (`--debug` / RTX 4070 Ti) eklenmesi.
- [x] Çoklu PCI ID veritabanı tarayıcısı (`/usr/share/hwdata/pci.ids` & `/usr/share/misc/pci.ids`) eklenmesi.
- [x] Debian harici ortamlarda çökmeleri önleyen `MockAptCache` katmanı eklenmesi.
- [x] `run.sh`, `stop.sh`, `install.sh`, `uninstall.sh`, `package.sh` ve `manage.sh` yönetim araçlarının yazılması.
- [x] Debian `.deb` ve Arch Linux `.pkg.tar.zst` paketlerinin başarıyla inşa edilmesi (`dist/`).
- [x] Birim test takımının oluşturulması (`tests/test_nvidia_installer.py`, 20/20 başarılı).
- [x] Tam standartlaştırılmış dokümantasyon seti (`docs/`) ve `.claudeignore` oluşturulması.
- [x] Gelişmiş Wayland / PRIME profil seçici arayüzü (🍃 Tasarruf / ⚡ Hibrit / 🚀 Performans).
- [x] Canlı telemetri, GPU sıcaklığı, fan hızı ve VRAM kullanım göstergeleri (`src/monitor.py`).
- [x] CUDA Toolkit, cuDNN ve TensorRT geliştirici kütüphaneleri için tek tıkla kurulum sihirbazı.
- [x] Özel GPU fan hızı (%20-%100) ve güç limiti (Power Limit TDP) ayarlayıcısı.
- [x] Oyun bazlı profil yönetimi (Steam, Lutris, Heroic oyunlarında otomatik NVIDIA PRIME offload).
- [x] Sistem tepsisi (AppIndicator / Tray) mini sıcaklık ve mod göstergesi (`src/tray.py`).
- [x] Modern 4 sekmeli (`Gtk.StackSwitcher`) kullanıcı arayüzü tasarımı.
- [x] **Kart Otomatik Algılama Sistemi (GPU Auto-Detection Engine)** (`src/detector.py`):
  - Çok katmanlı donanım tarama motoru (`sysfs`, `lspci -nn`, DRM ve PCI veritabanı).
  - Intel, AMD ve NVIDIA grafik yongalarını ve birincil/ikincil (Optimus/PRIME) rollerini eksiksiz algılama.
  - NVIDIA mimari tespiti (Blackwell, Ada Lovelace, Ampere, Turing, Volta, Pascal, Maxwell, Kepler, Fermi).
  - Akıllı Sürücü Tavsiye Motoru (`tag_recommended_driver`) ile mimariye en uygun sürücüyü belirleme.
  - Kullanıcı arayüzünde parlayan `★ ÖNERİLEN` rozeti ve tek tıkla "Önerilen Sürücüyü Otomatik Seç" aksiyonu.
  - Kapsamlı sistem GPU tanılama penceresi (Hardware Diagnostics Dialog) ve panoya kopyalama desteği.
  - Canlı donanım yeniden tarama (`Rescan Hardware`) ve farklı nesilleri test eden mimari simülatörü.
  - Terminal CLI desteği: `parslinux-nvidia-installer --detect` (`-d`) ve `--json` raporlama.
- [x] **GTK 4 & VTE 4 (vte-3.91) Tam Modernizasyonu (Saf GTK4 Mimarisi)**:
  - XML arayüz tanımlarının (`ui/ui.glade` ve `ui/driver_toggle.glade`) GTK4 Builder standartlarına dönüştürülmesi (`<requires lib="gtk" version="4.0"/>`, `GtkCheckButton`, `GtkStackPage`, `GtkHeaderBar title-widget`).
  - Python kodunun ([`src/Main.py`](file:///home/can/Masaüstü/proje/mcsm/masaüstü/inceleme_düzenleme/parslinux-nvidia-installer/src/Main.py), [`src/MainWindow.py`](file:///home/can/Masaüstü/proje/mcsm/masaüstü/inceleme_düzenleme/parslinux-nvidia-installer/src/MainWindow.py)) GTK 4.0 ve VTE 3.91 API'lerine uyarlanması.
  - GTK4 Box, ScrolledWindow, Label ve CenterBox uyumluluk katmanlarının entegrasyonu.
  - Modern GTK4 diyalogları (`present()`, non-blocking yanıt sinyalleri) ve sistem panosu entegrasyonu (`Gdk.Display.get_default().get_clipboard()`).
  - Bağımsız sistem tepsisi (AppIndicator/Tray) yönetimi ve arka plan süreç delegasyonu ([`src/tray.py`](file:///home/can/Masaüstü/proje/mcsm/masaüstü/inceleme_düzenleme/parslinux-nvidia-installer/src/tray.py)).
  - Debian ve Arch Linux paket bağımlılıklarının (`install.sh`, `PKGBUILD`, `debian/control`, `setup.py`) GTK4 olarak güncellenmesi.
- [x] **Gelişmiş GPU Hız Aşırtma (Overclocking)**:
  - Çekirdek (Core Clock -300..+400 MHz) ve Bellek (Memory Clock -1000..+2000 MHz) frekans ofset kaydırıcıları.
  - `nvidia-settings` komut desteği, güvenli değer doğrulaması ve kalıcı önbellekleme (`src/package.py`, `src/monitor.py`).
- [x] **Oyun İçi Canlı HUD / Telemetri (MangoHud Entegrasyonu)**:
  - Oyunlarda ekran üzeri FPS, GPU/CPU sıcaklığı, VRAM ve kare gecikmesi bilgisi katmanı.
  - Tek tıkla MangoHud yapılandırma profili üretici ve otomatik etkinleştirici.
- [x] **Yedekleme ve Geri Yükleme Noktaları (Timeshift Entegrasyonu)**:
  - Sürücü kurulumu veya güncellemesi öncesi tek tıkla Timeshift sistem anlık görüntüsü (snapshot) oluşturma.
  - Eksikse Timeshift tek tıkla kurulum sihirbazı desteği.
- [x] **Genişletilmiş Otomatik Test Takımı**:
  - GTK4 builder doğrulaması, simüle uygulama başlatma, MangoHud profili, Overclocking ve Timeshift doğrulamaları dahil 31/31 birim ve entegrasyon testi başarılı (`tests/test_nvidia_installer.py`).

---

## 🎯 Gelecek Hedefler (v1.4.0 & Yol Haritası)
- [ ] **Çoklu Monitör ve G-Sync / VRR Yapılandırma Asistanı**:
  - Wayland ve X11 ortamlarında adaptif senkronizasyon (VRR) otomatik ayarı.
- [ ] **Özel Fan Eğrisi (Custom Fan Curve) Profili**:
  - Sıcaklık eşiklerine göre kademeli dinamik fan devri kontrol servisi.
- [ ] **Vulkan / DXVK / Proton Oyun Uyumluluk Analizörü**:
  - Yüklü Vulkan kütüphanelerini ve Proton sürücü uyumluluğunu denetleyen grafik arayüz.
