#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ParsLinux Nvidia Installer - Hardware & GPU Auto-Detection System
Provides multi-layer hardware detection, architecture identification,
and smart driver recommendation.
"""

import os
import sys
import re
import json
import subprocess
from locale import gettext as _

NVIDIA_VENDOR_ID = 0x10DE
INTEL_VENDOR_ID = 0x8086
AMD_VENDOR_ID = 0x1002

# Architecture definitions & recommended driver mapping
ARCHITECTURES = {
    "Blackwell": {
        "name": "NVIDIA Blackwell",
        "description": _("Next-Gen Blackwell Architecture (RTX 5000 / B-Series)"),
        "min_id": 0x2900,
        "max_id": 0x2CFF,
        "recommended_package": "nvidia-driver",
        "min_driver_version": "570",
        "reason": _("Newest architecture, requires official modern production branch driver.")
    },
    "Ada Lovelace": {
        "name": "NVIDIA Ada Lovelace",
        "description": _("Ada Lovelace Architecture (RTX 4000 Series, DLSS 3.5 & AV1)"),
        "min_id": 0x2680,
        "max_id": 0x28FF,
        "recommended_package": "nvidia-driver",
        "min_driver_version": "550",
        "reason": _("Requires modern proprietary driver (550+ / 560+) for full DLSS 3, RT Core and NVENC support.")
    },
    "Ampere": {
        "name": "NVIDIA Ampere",
        "description": _("Ampere Architecture (RTX 3000 Series & A-Series)"),
        "min_id": 0x2200,
        "max_id": 0x25FF,
        "recommended_package": "nvidia-driver",
        "min_driver_version": "550",
        "reason": _("Fully supported by the latest official proprietary nvidia-driver branch.")
    },
    "Turing": {
        "name": "NVIDIA Turing",
        "description": _("Turing Architecture (RTX 2000 & GTX 1600 Series)"),
        "min_id": 0x1E00,
        "max_id": 0x21FF,
        "recommended_package": "nvidia-driver",
        "min_driver_version": "535",
        "reason": _("Supported by modern proprietary nvidia-driver (535+ / 550+).")
    },
    "Volta": {
        "name": "NVIDIA Volta",
        "description": _("Volta Architecture (Titan V, GV100)"),
        "min_id": 0x1D00,
        "max_id": 0x1DFF,
        "recommended_package": "nvidia-driver",
        "min_driver_version": "535",
        "reason": _("Supported by modern proprietary nvidia-driver branch.")
    },
    "Pascal": {
        "name": "NVIDIA Pascal",
        "description": _("Pascal Architecture (GTX 1000 Series)"),
        "min_id": 0x1B00,
        "max_id": 0x1CFF,
        "recommended_package": "nvidia-driver",
        "min_driver_version": "535",
        "reason": _("Supported by standard nvidia-driver branch.")
    },
    "Maxwell": {
        "name": "NVIDIA Maxwell",
        "description": _("Maxwell Architecture (GTX 900 Series & GTX 750 Ti)"),
        "min_id": 0x1340,
        "max_id": 0x17FF,
        "recommended_package": "nvidia-driver",
        "min_driver_version": "535",
        "reason": _("Supported by standard nvidia-driver branch.")
    },
    "Kepler": {
        "name": "NVIDIA Kepler",
        "description": _("Kepler Architecture (GTX 600 & 700 Series Legacy)"),
        "min_id": 0x0FC0,
        "max_id": 0x1200,
        "recommended_package": "nvidia-tesla-470-driver",
        "min_driver_version": "470",
        "reason": _("Official driver support ended at 470.xx branch. Use nvidia-tesla-470-driver.")
    },
    "Fermi": {
        "name": "NVIDIA Fermi",
        "description": _("Fermi Architecture (GTX 400 & 500 Series Legacy)"),
        "min_id": 0x0DC0,
        "max_id": 0x0FF0,
        "recommended_package": "nvidia-legacy-390xx-driver",
        "min_driver_version": "390",
        "reason": _("Official driver support ended at 390.xx branch. Use nvidia-legacy-390xx-driver.")
    },
    "Tesla": {
        "name": "NVIDIA Tesla / Legacy",
        "description": _("Legacy GeForce 8/9/200 Series"),
        "min_id": 0x0190,
        "max_id": 0x0A00,
        "recommended_package": "xserver-xorg-video-nouveau",
        "min_driver_version": "340",
        "reason": _("End-of-life hardware. Open-source Nouveau driver is recommended for modern kernels.")
    }
}


def get_pci_database():
    """Load PCI ID names from system files."""
    paths = [
        "/usr/share/misc/pci.ids",
        "/usr/share/hwdata/pci.ids",
        "/usr/share/pci.ids",
    ]
    pci_path = None
    for p in paths:
        if os.path.isfile(p):
            pci_path = p
            break
    if not pci_path:
        return {}

    pci_db = {}
    cur_vendor = None
    try:
        with open(pci_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                if not line.startswith("\t"):
                    parts = line.strip().split(" ", 1)
                    try:
                        cur_vendor = int(parts[0], 16)
                        pci_db[cur_vendor] = {
                            "name": parts[1].strip() if len(parts) > 1 else "Unknown Vendor",
                            "devices": {}
                        }
                    except ValueError:
                        cur_vendor = None
                else:
                    if cur_vendor is None or line.startswith("\t\t"):
                        continue
                    parts = line.strip().split(" ", 1)
                    try:
                        dev_id = int(parts[0], 16)
                        dev_name = parts[1].strip() if len(parts) > 1 else f"Device {dev_id:04x}"
                        pci_db[cur_vendor]["devices"][dev_id] = dev_name
                    except ValueError:
                        continue
    except Exception as e:
        print(f"Warning: Failed to load pci.ids: {e}", file=sys.stderr)
    return pci_db


def get_nvidia_pci_json_db():
    """Load nvidia-pci.json mapping device IDs to model names and drivers."""
    json_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "../data/nvidia-pci.json"))
    if not os.path.isfile(json_path):
        return {}
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.loads(f.read())
    except Exception:
        return {}


def identify_architecture(device_id_int, device_name=""):
    """
    Given a PCI device ID and optional name, determine the NVIDIA architecture,
    recommended package name, and reason.
    """
    if not device_id_int:
        return "Unknown", _("Bilinmeyen Mimari"), "nvidia-driver", _("Otomatik tespit")

    # Name-based heuristic overrides (very reliable for modern consumer GPUs)
    name_upper = (device_name or "").upper()
    if "RTX 50" in name_upper or "BLACKWELL" in name_upper:
        a = ARCHITECTURES["Blackwell"]
        return "Blackwell", a["description"], a["recommended_package"], a["reason"]
    if "RTX 40" in name_upper or "AD10" in name_upper:
        a = ARCHITECTURES["Ada Lovelace"]
        return "Ada Lovelace", a["description"], a["recommended_package"], a["reason"]
    if "RTX 30" in name_upper or "GA10" in name_upper or "A100" in name_upper or "A6000" in name_upper:
        a = ARCHITECTURES["Ampere"]
        return "Ampere", a["description"], a["recommended_package"], a["reason"]
    if "RTX 20" in name_upper or "GTX 16" in name_upper or "TU11" in name_upper or "TU10" in name_upper:
        a = ARCHITECTURES["Turing"]
        return "Turing", a["description"], a["recommended_package"], a["reason"]
    if "TITAN V" in name_upper or "GV100" in name_upper:
        a = ARCHITECTURES["Volta"]
        return "Volta", a["description"], a["recommended_package"], a["reason"]
    if "GTX 10" in name_upper or "GP10" in name_upper:
        a = ARCHITECTURES["Pascal"]
        return "Pascal", a["description"], a["recommended_package"], a["reason"]
    if "GTX 9" in name_upper or "GTX 750" in name_upper or "GM20" in name_upper or "GM10" in name_upper:
        a = ARCHITECTURES["Maxwell"]
        return "Maxwell", a["description"], a["recommended_package"], a["reason"]
    if any(k in name_upper for k in ("GTX 780", "GTX 770", "GTX 760", "GTX 680", "GTX 670", "GTX 660", "GK10", "GK11")):
        a = ARCHITECTURES["Kepler"]
        return "Kepler", a["description"], a["recommended_package"], a["reason"]
    if any(f in name_upper for f in ("GTX 580", "GTX 570", "GTX 560", "GTX 480", "GTX 470", "GTX 460", "GF10", "GF11")):
        a = ARCHITECTURES["Fermi"]
        return "Fermi", a["description"], a["recommended_package"], a["reason"]

    # Device ID ranges
    for arch_key, info in ARCHITECTURES.items():
        if info["min_id"] <= device_id_int <= info["max_id"]:
            return arch_key, info["description"], info["recommended_package"], info["reason"]

    # Check against nvidia-pci.json driver databases
    dev_hex = f"{device_id_int:04X}"
    pci_json = get_nvidia_pci_json_db()
    for drv_key in ("nvidia-legacy-390xx-driver", "nvidia-tesla-470-driver", "nvidia-driver"):
        if drv_key in pci_json and dev_hex in pci_json[drv_key]:
            if drv_key == "nvidia-tesla-470-driver":
                return "Kepler", ARCHITECTURES["Kepler"]["description"], drv_key, ARCHITECTURES["Kepler"]["reason"]
            elif drv_key == "nvidia-legacy-390xx-driver":
                return "Fermi", ARCHITECTURES["Fermi"]["description"], drv_key, ARCHITECTURES["Fermi"]["reason"]
            else:
                return "Modern NVIDIA", _("NVIDIA Modern Mimarisi"), "nvidia-driver", _("Resmi nvidia-driver önerilmektedir.")

    # Default fallback
    return "NVIDIA GPU", _("Standart NVIDIA Mimarisi"), "nvidia-driver", _("Modern nvidia-driver önerilmektedir.")


def read_sysfs_file(path):
    """Safely read string from a sysfs file."""
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read().strip()
        except OSError:
            pass
    return None


def detect_all_system_gpus():
    """
    Comprehensive scan of all graphics adapters on the system.
    Returns a list of dictionaries with details for Intel, AMD, NVIDIA, etc.
    """
    gpus = []
    pci_dev_path = "/sys/bus/pci/devices/"
    pci_db = get_pci_database()
    pci_json = get_nvidia_pci_json_db()

    # 1. Sysfs detection
    if os.path.exists(pci_dev_path):
        for slot in sorted(os.listdir(pci_dev_path)):
            dev_dir = os.path.join(pci_dev_path, slot)
            class_str = read_sysfs_file(os.path.join(dev_dir, "class"))
            if not class_str or not class_str.startswith("0x03"):
                continue  # 0x0300 = VGA, 0x0302 = 3D controller, 0x0380 = Display controller

            vendor_str = read_sysfs_file(os.path.join(dev_dir, "vendor"))
            device_str = read_sysfs_file(os.path.join(dev_dir, "device"))
            if not vendor_str or not device_str:
                continue

            try:
                vendor_id = int(vendor_str, 16)
                device_id = int(device_str, 16)
            except (ValueError, TypeError):
                continue

            boot_vga = read_sysfs_file(os.path.join(dev_dir, "boot_vga"))
            is_primary = (boot_vga == "1")

            # Active kernel driver module
            driver_mod = None
            driver_ver = None
            drv_link = os.path.join(dev_dir, "driver", "module")
            if os.path.islink(drv_link):
                try:
                    driver_mod = os.path.basename(os.readlink(drv_link))
                    driver_ver = read_sysfs_file(os.path.join(drv_link, "version"))
                except OSError:
                    pass

            # Subsystem
            subsystem_dev = read_sysfs_file(os.path.join(dev_dir, "subsystem_device"))
            subsystem_vendor = read_sysfs_file(os.path.join(dev_dir, "subsystem_vendor"))

            # Vendor and model names
            vendor_name = "Unknown Vendor"
            if vendor_id == NVIDIA_VENDOR_ID:
                vendor_name = "NVIDIA Corporation"
            elif vendor_id == INTEL_VENDOR_ID:
                vendor_name = "Intel Corporation"
            elif vendor_id == AMD_VENDOR_ID:
                vendor_name = "Advanced Micro Devices, Inc. [AMD/ATI]"
            elif vendor_id in pci_db:
                vendor_name = pci_db[vendor_id].get("name", "Unknown Vendor")

            device_hex = f"{device_id:04X}"
            device_name = None

            # Try nvidia-pci.json first for exact NVIDIA branding
            if vendor_id == NVIDIA_VENDOR_ID:
                for drv_key in pci_json:
                    if device_hex in pci_json[drv_key]:
                        device_name = pci_json[drv_key][device_hex]
                        break

            # Next check pci.ids
            if not device_name and vendor_id in pci_db:
                device_name = pci_db[vendor_id].get("devices", {}).get(device_id)

            if not device_name:
                device_name = f"PCI Device [{vendor_id:04x}:{device_id:04x}]"

            # Architecture & recommended driver for NVIDIA
            arch = None
            arch_desc = None
            rec_pkg = None
            rec_reason = None
            if vendor_id == NVIDIA_VENDOR_ID:
                arch, arch_desc, rec_pkg, rec_reason = identify_architecture(device_id, device_name)

            gpu_info = {
                "pci_slot": slot,
                "vendor_id": vendor_id,
                "vendor_id_hex": f"{vendor_id:04X}",
                "vendor_name": vendor_name,
                "device_id": device_id,
                "device_id_hex": device_hex,
                "device_name": device_name,
                "is_primary": is_primary,
                "is_nvidia": (vendor_id == NVIDIA_VENDOR_ID),
                "driver_module": driver_mod,
                "driver_version": driver_ver,
                "subsystem_vendor": subsystem_vendor,
                "subsystem_device": subsystem_dev,
                "architecture": arch,
                "architecture_desc": arch_desc,
                "recommended_driver": rec_pkg,
                "recommendation_reason": rec_reason,
            }
            gpus.append(gpu_info)

    # 2. Fallback to lspci if sysfs found nothing
    if not gpus:
        try:
            out = subprocess.check_output(["lspci", "-nn", "-D"], text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                line_lower = line.lower()
                if any(t in line_lower for t in ("vga compatible", "3d controller", "display controller")):
                    match = re.search(r"^([0-9a-fA-F:.]+)\s+([^:]+):\s+(.+?)\s+\[([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\]", line)
                    if match:
                        slot, _, name, v_hex, d_hex = match.groups()
                        v_id = int(v_hex, 16)
                        d_id = int(d_hex, 16)
                        is_nv = (v_id == NVIDIA_VENDOR_ID)
                        arch, arch_desc, rec_pkg, rec_reason = None, None, None, None
                        if is_nv:
                            arch, arch_desc, rec_pkg, rec_reason = identify_architecture(d_id, name)
                        gpus.append({
                            "pci_slot": slot,
                            "vendor_id": v_id,
                            "vendor_id_hex": v_hex.upper(),
                            "vendor_name": "NVIDIA Corporation" if is_nv else "Graphics Adapter",
                            "device_id": d_id,
                            "device_id_hex": d_hex.upper(),
                            "device_name": name.strip(),
                            "is_primary": ("vga" in line_lower),
                            "is_nvidia": is_nv,
                            "driver_module": None,
                            "driver_version": None,
                            "subsystem_vendor": None,
                            "subsystem_device": None,
                            "architecture": arch,
                            "architecture_desc": arch_desc,
                            "recommended_driver": rec_pkg,
                            "recommendation_reason": rec_reason,
                        })
        except Exception:
            pass

    return gpus


def get_detected_nvidia_gpus():
    """Returns only detected NVIDIA graphics cards."""
    all_gpus = detect_all_system_gpus()
    return [g for g in all_gpus if g["is_nvidia"]]


def tag_recommended_driver(driver_list, gpus=None):
    """
    Given a list of NvidiaDriver instances and detected GPUs, determines
    which driver is the best recommendation and sets driver.is_recommended = True.
    Returns the recommended driver instance or None.
    """
    if not driver_list:
        return None

    # Reset existing recommendations
    for d in driver_list:
        d.is_recommended = False
        d.recommendation_reason = ""

    if not gpus:
        # Fallback: prefer installed proprietary or highest version nvidia-driver
        for d in driver_list:
            if d.package == "nvidia-driver" and d.repo == "NVIDIA":
                d.is_recommended = True
                d.recommendation_reason = _("Resmi NVIDIA sürücüsü (En kararlı ve güncel)")
                return d
        driver_list[0].is_recommended = True
        return driver_list[0]

    # Find target recommended package from the first NVIDIA GPU
    target_pkg = "nvidia-driver"
    reason = _("Modern NVIDIA mimarisi için önerilmektedir.")

    for g in gpus:
        if hasattr(g, "recommended_driver") and g.recommended_driver:
            target_pkg = g.recommended_driver
            reason = getattr(g, "recommendation_reason", reason)
            break
        elif isinstance(g, dict) and g.get("recommended_driver"):
            target_pkg = g["recommended_driver"]
            reason = g.get("recommendation_reason", reason)
            break

    # Match best driver from available list
    # Preference priority:
    # 1. Exact package match from NVIDIA repo
    # 2. Exact package match from Distro repo
    # 3. Any nvidia-driver
    # 4. First item
    matched = None
    for d in driver_list:
        if d.package == target_pkg and getattr(d, "repo", "") == "NVIDIA":
            matched = d
            break
    if not matched:
        for d in driver_list:
            if d.package == target_pkg:
                matched = d
                break
    if not matched:
        for d in driver_list:
            if d.package == "nvidia-driver":
                matched = d
                break
    if not matched and len(driver_list) > 0:
        matched = driver_list[0]

    if matched:
        matched.is_recommended = True
        matched.recommendation_reason = reason

    return matched


def generate_hardware_report():
    """
    Generates a full textual diagnostic report for CLI and UI inspector.
    """
    all_gpus = detect_all_system_gpus()
    lines = []
    lines.append("=" * 66)
    lines.append("  ParsLinux Donanım & GPU Otomatik Algılama Raporu")
    lines.append("=" * 66)

    if not all_gpus:
        lines.append("  [!] Sistemde hiçbir PCI grafik bağdaştırıcısı algılanamadı.")
        lines.append("=" * 66)
        return "\n".join(lines)

    lines.append(f"  Toplam Tespit Edilen Grafik Birimi: {len(all_gpus)}\n")
    for idx, g in enumerate(all_gpus):
        tag = "[Birincil Görüntü (Primary)]" if g["is_primary"] else "[İkincil / Harici (Discrete)]"
        lines.append(f"  GPU #{idx + 1}: {g['device_name']}")
        lines.append(f"    ├─ Durum:       {tag}")
        lines.append(f"    ├─ Üretici:     {g['vendor_name']} (0x{g['vendor_id_hex']})")
        lines.append(f"    ├─ Donanım ID:  {g['vendor_id_hex']}:{g['device_id_hex']}")
        lines.append(f"    ├─ PCI Veriyolu:{g['pci_slot']}")
        lines.append(f"    ├─ Aktif Modül: {g['driver_module'] or 'Yüklü Değil / Bilinmiyor'}")
        if g.get("driver_version"):
            lines.append(f"    ├─ Sürücü Sür.: {g['driver_version']}")
        if g["is_nvidia"]:
            lines.append(f"    ├─ Mimari:      {g.get('architecture', 'Bilinmiyor')}")
            lines.append(f"    ├─ Önerilen:    {g.get('recommended_driver', 'nvidia-driver')}")
            lines.append(f"    └─ Gerekçe:     {g.get('recommendation_reason', 'Otomatik tespit')}")
        else:
            lines.append(f"    └─ Not:         NVIDIA dışı bağdaştırıcı (Intel / AMD / Sanal)")
        lines.append("")

    lines.append("=" * 66)
    return "\n".join(lines)
