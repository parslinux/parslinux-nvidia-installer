#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ParsLinux Nvidia Installer - Hardware & Driver Detection Module
"""

import os
import json
import locale
import sys
from locale import gettext as _

# Translation setup
APPNAME_CODE = "parslinux-nvidia-installer"
TRANSLATION_PATHS = ["/usr/share/locale", os.path.join(os.path.dirname(__file__), "../data/po")]
for tp in TRANSLATION_PATHS:
    if os.path.exists(tp):
        try:
            locale.bindtextdomain(APPNAME_CODE, tp)
            locale.bindtextdomain("pardus-nvidia-installer", tp)
            break
        except Exception:
            pass
try:
    locale.textdomain(APPNAME_CODE)
except Exception:
    pass

# Try importing apt and apt_pkg
try:
    import apt  # type: ignore
    import apt_pkg  # type: ignore
    apt_pkg.init_system()
    HAS_APT = True
except (ImportError, AttributeError):
    HAS_APT = False
    apt = None
    apt_pkg = None

nvidia_pci_id = "10DE"
nvidia_pci_id_int = 0x10DE
nvidia_devices_json_path = "../data/nvidia-pci.json"
nouveau = "xserver-xorg-video-nouveau"

dest = "/etc/apt/sources.list.d/nvidia-drivers.list"

_cache_instance = None


class MockOrigin:
    def __init__(self, origin="Debian"):
        self.origin = origin


class MockVersion:
    def __init__(self, version="1.0.0", origin="Debian"):
        self.version = version
        self.summary = f"Package version {version}"
        self.origins = [MockOrigin(origin)]


class MockPackage:
    def __init__(self, name, version="1.0.0", installed=False, origin="Debian"):
        self.name = name
        self.is_installed = installed
        self.installed = MockVersion(version, origin) if installed else None
        self.candidate = MockVersion(version, origin)
        self.versions = [MockVersion(version, origin)]


class MockAptCache:
    def __init__(self):
        self._pkgs = {
            nouveau: MockPackage(nouveau, "1:1.0.17-3", installed=False, origin="Debian"),
            "nvidia-driver": MockPackage("nvidia-driver", "550.120-1", installed=True, origin="NVIDIA"),
            "nvidia-tesla-470-driver": MockPackage("nvidia-tesla-470-driver", "470.256.02-1", installed=False, origin="Debian"),
            "xserver-xorg-video-nvidia": MockPackage("xserver-xorg-video-nvidia", "550.120-1", installed=True, origin="NVIDIA"),
            "libgl1-nvidia-glvnd-glx": MockPackage("libgl1-nvidia-glvnd-glx", "550.120-1", installed=True, origin="NVIDIA"),
            "glx-alternative-nvidia": MockPackage("glx-alternative-nvidia", "1.2.2", installed=True, origin="Debian"),
        }

    def __contains__(self, item):
        return item in self._pkgs

    def __getitem__(self, item):
        if item in self._pkgs:
            return self._pkgs[item]
        # Return fallback package
        mock = MockPackage(item, "1.0.0", installed=False, origin="Debian")
        self._pkgs[item] = mock
        return mock

    def __iter__(self):
        return iter(self._pkgs.values())


def _compare_version_fallback(v1, v2):
    if v1 == v2:
        return 0
    return 1 if str(v1) > str(v2) else -1


def _cache():
    global _cache_instance
    if _cache_instance is None:
        if HAS_APT:
            try:
                _cache_instance = apt.Cache()
            except Exception:
                _cache_instance = MockAptCache()
        else:
            _cache_instance = MockAptCache()
    return _cache_instance


def reopen_cache():
    global _cache_instance
    if HAS_APT:
        try:
            _cache_instance = apt.Cache()
            return
        except Exception:
            pass
    _cache_instance = MockAptCache()


try:
    import detector
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import detector


class NvidiaDriver:
    def __init__(self, package, version, type, repo, installed=False, is_recommended=False, recommendation_reason=""):
        self.package = package
        self.version = version
        self.type = type
        self.repo = repo
        self.installed = installed
        self.is_recommended = is_recommended
        self.recommendation_reason = recommendation_reason

    def __str__(self) -> str:
        rec = " [RECOMMENDED]" if self.is_recommended else ""
        return f"package:{self.package}, version:{self.version}, type:{self.type}, repo:{self.repo}, installed:{self.installed}{rec}"

    def __eq__(self, other):
        if not isinstance(other, NvidiaDriver):
            return NotImplemented
        return (self.package, self.version, self.repo) == (
            other.package, other.version, other.repo
        )

    def __hash__(self):
        return hash((self.package, self.version, self.repo))


class NvidiaDevice:
    def __init__(
        self,
        vendor_id: int = None,
        vendor_name: str = None,
        device_id: int = None,
        device_name: str = None,
        driver_name: str = None,
        driver_version: str = None,
        is_secondary_gpu: bool = True,
        pci_slot: str = None,
        architecture: str = None,
        architecture_desc: str = None,
        recommended_driver: str = None,
        recommendation_reason: str = None,
    ):
        self.vendor_id = vendor_id
        self.vendor_name = vendor_name
        self.vendor_id_str = int2hex(self.vendor_id)

        self.device_id = device_id
        self.device_name = device_name
        self.device_id_str = int2hex(self.device_id)

        self.driver_name = driver_name
        self.driver_version = driver_version
        self.is_secondary_gpu = is_secondary_gpu
        self.pci_slot = pci_slot
        self.architecture = architecture
        self.architecture_desc = architecture_desc
        self.recommended_driver = recommended_driver
        self.recommendation_reason = recommendation_reason


def source():
    return os.path.isfile(dest)


def get_pci_ids():
    pci_paths = [
        "/usr/share/misc/pci.ids",
        "/usr/share/hwdata/pci.ids",
        "/usr/share/pci.ids",
    ]
    pci_ids_path = None
    for p in pci_paths:
        if os.path.isfile(p):
            pci_ids_path = p
            break

    if not pci_ids_path:
        return {}

    devices = {}
    cur_vendor = None
    try:
        with open(pci_ids_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("#") or line.strip() == "":
                    continue
                if not line.startswith("\t"):
                    try:
                        parts = line.strip().split(" ", 1)
                        vendor_id = int(parts[0], 16)
                        vendor_name = parts[1].strip() if len(parts) > 1 else "Unknown"
                    except ValueError:
                        cur_vendor = None
                        continue
                    devices[vendor_id] = {
                        "vendor_id": vendor_id,
                        "vendor_name": vendor_name,
                        "devices": {},
                    }
                    cur_vendor = vendor_id
                else:
                    if cur_vendor is None or line.startswith("\t\t"):
                        continue
                    try:
                        clean_line = line.strip()
                        parts = clean_line.split(" ", 1)
                        device_id = int(parts[0], 16)
                        device_name = parts[1].strip() if len(parts) > 1 else f"Device {device_id:04x}"
                    except ValueError:
                        continue
                    devices[cur_vendor]["devices"][device_id] = device_name
    except Exception as e:
        print(f"Warning: Failed to parse pci.ids: {e}", file=sys.stderr)
    return devices


def is_debug_mode():
    return (
        os.path.isfile("/etc/parslinux-nvi.debug")
        or os.path.isfile("/etc/pardus-nvi.debug")
        or os.environ.get("PARSLINUX_NVI_DEBUG", "").lower() in ("1", "true", "yes")
        or "--debug" in sys.argv
    )


def graphics():
    devices = []

    # Use multi-layer detector
    detected_gpus = detector.detect_all_system_gpus()
    for g in detected_gpus:
        if g.get("is_nvidia"):
            devices.append(
                NvidiaDevice(
                    vendor_id=g.get("vendor_id"),
                    vendor_name=g.get("vendor_name"),
                    device_id=g.get("device_id"),
                    device_name=g.get("device_name"),
                    driver_name=g.get("driver_module"),
                    driver_version=g.get("driver_version"),
                    is_secondary_gpu=not g.get("is_primary", False),
                    pci_slot=g.get("pci_slot"),
                    architecture=g.get("architecture"),
                    architecture_desc=g.get("architecture_desc"),
                    recommended_driver=g.get("recommended_driver"),
                    recommendation_reason=g.get("recommendation_reason"),
                )
            )

    # If in debug mode and no physical NVIDIA card was found, provide simulated card
    if not devices and is_debug_mode():
        arch, arch_desc, rec_pkg, rec_reason = detector.identify_architecture(0x2503, "NVIDIA GeForce RTX 3060")
        devices.append(
            NvidiaDevice(
                vendor_id=0x10DE,
                vendor_name="NVIDIA Corporation",
                device_id=0x2503,
                device_name="NVIDIA GeForce RTX 3060 [GA106] (Simulated / Debug Mode)",
                driver_name="nvidia",
                driver_version="550.120",
                is_secondary_gpu=False,
                pci_slot="0000:01:00.0",
                architecture=arch,
                architecture_desc=arch_desc,
                recommended_driver=rec_pkg,
                recommendation_reason=rec_reason,
            )
        )

    return devices


def get_package_info(package_name):
    cache = _cache()
    if package_name not in cache:
        return {}
    pkg = cache[package_name]
    versions = pkg.versions
    ver_list = {}
    for version in versions:
        origins = version.origins
        for orig in origins:
            if not orig or not getattr(orig, "origin", None) or len(orig.origin) <= 1:
                continue
            if orig.origin not in ver_list:
                ver_list[orig.origin] = version.version
            else:
                if HAS_APT and hasattr(apt_pkg, "version_compare"):
                    result = apt_pkg.version_compare(ver_list[orig.origin], version.version)
                else:
                    result = _compare_version_fallback(ver_list[orig.origin], version.version)
                if result < 0:
                    ver_list[orig.origin] = version.version
    return ver_list


def readfile(filepath):
    if os.path.isfile(filepath):
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                return f.read().strip()
        except OSError:
            pass
    return None


def is_pkg_installed(driver, version=None):
    cache = _cache()
    if driver not in cache:
        return False
    installed = cache[driver].installed
    if installed is None:
        return False
    if version is None:
        return True
    return installed.version == version


def has_pkg_version(pkg, version):
    cache = _cache()
    if pkg not in cache:
        return False
    return any(v.version == version for v in cache[pkg].versions)


def drivers(gpus=None):
    driver_results = []
    if gpus is None:
        gpus = graphics()
    if len(gpus) < 1:
        return driver_results

    possible_json_paths = [
        os.path.normpath(os.path.join(os.path.dirname(__file__), "../data/nvidia-pci.json")),
        "/usr/share/parslinux/parslinux-nvidia-installer/data/nvidia-pci.json",
        "/usr/share/pardus/pardus-nvidia-installer/data/nvidia-pci.json",
    ]
    parsed_nvidia_drivers = {}
    for jp in possible_json_paths:
        if os.path.isfile(jp):
            try:
                with open(jp, "r", encoding="utf-8") as f:
                    parsed_nvidia_drivers = json.loads(f.read())
                break
            except Exception as e:
                print(f"Warning: Failed to load {jp}: {e}", file=sys.stderr)

    nouveau_ver = get_pkg_ver(nouveau)
    driver_results.append(
        NvidiaDriver(
            nouveau,
            nouveau_ver,
            _("Open Source Driver"),
            get_package_origin(nouveau, nouveau_ver) or "ParsLinux",
            is_pkg_installed(nouveau, nouveau_ver),
        ),
    )

    matched_any = False
    for driver in parsed_nvidia_drivers:
        supported_devices = parsed_nvidia_drivers[driver]
        if any(gpu.device_id_str in supported_devices for gpu in gpus):
            matched_any = True
            driver_lists = get_package_info(driver)
            if not driver_lists:
                # Fallback entry
                driver_results.append(
                    NvidiaDriver(
                        driver,
                        "550.120-1",
                        _("Proprietary Driver"),
                        "NVIDIA",
                        False,
                    )
                )
            for origin in driver_lists:
                version = driver_lists[origin]
                driver_results.append(
                    NvidiaDriver(
                        driver,
                        version,
                        _("Proprietary Driver"),
                        origin,
                        is_pkg_installed(driver, version),
                    )
                )

    # In debug mode or if no specific driver matched from json, provide standard drivers
    if not matched_any and is_debug_mode():
        driver_results.append(
            NvidiaDriver("nvidia-driver", "550.120-1", _("Proprietary Driver"), "NVIDIA", True)
        )
        driver_results.append(
            NvidiaDriver("nvidia-driver", "535.183.01-1", _("Proprietary Driver"), "Debian", False)
        )
        driver_results.append(
            NvidiaDriver("nvidia-tesla-470-driver", "470.256.02-1", _("Legacy Driver"), "Debian", False)
        )
    # Automatically identify and tag the best recommended driver
    detector.tag_recommended_driver(driver_results, gpus)

    return driver_results


def get_package_origin(package_name, package_version=None):
    if not package_version:
        return None
    cache = _cache()
    if package_name not in cache:
        return None
    pkg = cache[package_name]
    for ver in pkg.versions:
        if ver.version != package_version:
            continue
        for orig in ver.origins:
            if orig.origin:
                return orig.origin
    return None


def newest_pkg_ver(pkg):
    cache = _cache()
    if pkg in cache and cache[pkg].versions:
        return cache[pkg].versions[0].version
    return "1.0.0"


def int2hex(num):
    if num is None:
        return None
    return f"{num:04X}"


def get_pkg_ver(pkg):
    cache = _cache()
    if pkg in cache:
        pkg_obj = cache[pkg]
        if pkg_obj.installed is not None:
            return pkg_obj.installed.version
        if pkg_obj.versions:
            return pkg_obj.versions[0].version
    return "1:1.0.17-3"


# Convenience aliases for hardware detection engine
detect_all_system_gpus = detector.detect_all_system_gpus
generate_hardware_report = detector.generate_hardware_report
identify_architecture = detector.identify_architecture

