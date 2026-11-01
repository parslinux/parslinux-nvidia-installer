#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ParsLinux Nvidia Installer - Unit & Integration Test Suite
"""
import unittest
import os
import sys
import xml.etree.ElementTree as ET

# Add src to path
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import nvidia
import package

class TestNvidiaModel(unittest.TestCase):
    def test_nvidia_device_model(self):
        dev = nvidia.NvidiaDevice(
            vendor_id=0x10DE,
            vendor_name="NVIDIA Corporation",
            device_id=0x2503,
            device_name="GeForce RTX 3060",
            driver_name="nvidia",
            driver_version="550.120",
            is_secondary_gpu=False,
        )
        self.assertEqual(dev.vendor_id_str, "10DE")
        self.assertEqual(dev.device_id_str, "2503")
        self.assertFalse(dev.is_secondary_gpu)
        self.assertEqual(dev.device_name, "GeForce RTX 3060")

    def test_int2hex(self):
        self.assertEqual(nvidia.int2hex(0x10DE), "10DE")
        self.assertEqual(nvidia.int2hex(0x00FF), "00FF")
        self.assertEqual(nvidia.int2hex(0), "0000")
        self.assertIsNone(nvidia.int2hex(None))

    def test_nvidia_driver_equality(self):
        d1 = nvidia.NvidiaDriver("nvidia-driver", "550.120", "Proprietary", "NVIDIA", True)
        d2 = nvidia.NvidiaDriver("nvidia-driver", "550.120", "Proprietary", "NVIDIA", False)
        d3 = nvidia.NvidiaDriver("nvidia-driver", "535.183", "Proprietary", "Debian", False)
        self.assertEqual(d1, d2)
        self.assertNotEqual(d1, d3)
        self.assertIn("nvidia-driver", str(d1))

    def test_debug_mode_graphics(self):
        # Enable debug flag
        os.environ["PARSLINUX_NVI_DEBUG"] = "1"
        try:
            gpus = nvidia.graphics()
            self.assertGreater(len(gpus), 0)
            self.assertTrue(any("NVIDIA" in g.vendor_name or "NVIDIA" in g.device_name for g in gpus))
            
            # Drivers detection with simulated GPUs
            drvs = nvidia.drivers(gpus)
            self.assertGreater(len(drvs), 0)
            pkg_names = [d.package for d in drvs]
            self.assertIn("xserver-xorg-video-nouveau", pkg_names)
        finally:
            os.environ.pop("PARSLINUX_NVI_DEBUG", None)


class TestPackageSecurity(unittest.TestCase):
    def test_allowed_package_names(self):
        self.assertTrue(package._is_allowed_package("xserver-xorg-video-nouveau"))
        self.assertTrue(package._is_allowed_package("nvidia-driver"))
        self.assertTrue(package._is_allowed_package("nvidia-tesla-470-driver"))
        self.assertTrue(package._is_allowed_package("nvidia-driver=550.120-1"))
        self.assertTrue(package._is_allowed_package("linux-headers-6.6.0-pars-amd64"))
        self.assertTrue(package._is_allowed_package("xserver-xorg-video-nvidia"))
        self.assertTrue(package._is_allowed_package("libgl1-nvidia-glvnd-glx"))
        self.assertTrue(package._is_allowed_package("glx-alternative-nvidia"))

    def test_rejected_unsafe_package_names(self):
        # Prevent option injection or path traversal
        self.assertFalse(package._is_allowed_package("--reinstall"))
        self.assertFalse(package._is_allowed_package("curl"))
        self.assertFalse(package._is_allowed_package("../../../etc/shadow"))
        self.assertFalse(package._is_allowed_package("nvidia-driver; rm -rf /"))
        self.assertFalse(package._is_allowed_package(""))
        self.assertFalse(package._is_allowed_package("nvidia-driver=550.120;reboot"))

    def test_split_pkg(self):
        name, ver = package._split_pkg("nvidia-driver=550.120-1")
        self.assertEqual(name, "nvidia-driver")
        self.assertEqual(ver, "550.120-1")

        name2, ver2 = package._split_pkg("xserver-xorg-video-nouveau")
        self.assertEqual(name2, "xserver-xorg-video-nouveau")
        self.assertIsNone(ver2)

    def test_cuda_repo_distro_detection(self):
        distro = package.cuda_repo_distro()
        self.assertTrue(distro.startswith("debian"))
        self.assertIn(distro, ("debian12", "debian13"))


class TestMonitorAndTelemetry(unittest.TestCase):
    def test_gpu_telemetry_simulated(self):
        import monitor
        data = monitor.get_gpu_telemetry(simulated=True)
        self.assertTrue(data["available"])
        self.assertTrue(data["simulated"])
        self.assertIn("RTX 4070 Ti", data["name"])
        self.assertGreaterEqual(data["temp"], 30)
        self.assertLessEqual(data["temp"], 90)
        self.assertGreater(data["vram_total"], 0)
        self.assertGreaterEqual(data["vram_used"], 0)
        self.assertGreaterEqual(data["power"], 10)

    def test_prime_profile_detection(self):
        import monitor
        profile = monitor.get_prime_profile()
        self.assertIn(profile, ("integrated", "on-demand", "nvidia"))

    def test_ai_stack_detection(self):
        import monitor
        status = monitor.get_ai_stack_status()
        self.assertIn("cuda", status)
        self.assertIn("cudnn", status)
        self.assertIn("tensorrt", status)
        self.assertIn("installed", status["cuda"])

    def test_prime_mode_validation(self):
        self.assertFalse(package.set_prime_mode("invalid_mode"))
        self.assertFalse(package.set_prime_mode(""))

    def test_ai_package_whitelisting(self):
        self.assertTrue(package._is_allowed_package("nvidia-cuda-toolkit"))
        self.assertTrue(package._is_allowed_package("libcudnn8"))
        self.assertTrue(package._is_allowed_package("libcudnn8-dev"))
        self.assertTrue(package._is_allowed_package("libnvinfer8"))
        self.assertTrue(package._is_allowed_package("tensorrt"))
        self.assertTrue(package._is_allowed_package("nvidia-prime"))

    def test_fan_and_power_validation(self):
        self.assertFalse(package.set_fan_speed(-10))
        self.assertFalse(package.set_fan_speed(150))
        self.assertFalse(package.set_power_limit(10))
        self.assertFalse(package.set_power_limit(900))

    def test_gaming_helpers(self):
        import monitor
        launchers = monitor.get_detected_game_launchers()
        self.assertIsInstance(launchers, list)
        self.assertTrue(any(l["id"] == "steam" for l in launchers))
        offload_status = monitor.get_game_offload_status()
        self.assertIsInstance(offload_status, bool)

    def test_mangohud_profile_configuration(self):
        import monitor
        status = monitor.get_mangohud_status()
        self.assertIn("installed", status)
        self.assertIn("enabled", status)

        # Test enabling and disabling profile
        ok = monitor.set_mangohud_profile(True)
        self.assertTrue(ok)
        self.assertTrue(monitor.get_mangohud_status()["enabled"])

        # Revert
        monitor.set_mangohud_profile(False)
        self.assertFalse(monitor.get_mangohud_status()["enabled"])

    def test_overclock_settings_and_validation(self):
        import monitor
        self.assertFalse(package.set_gpu_overclock(-500, 0))
        self.assertFalse(package.set_gpu_overclock(600, 0))
        self.assertFalse(package.set_gpu_overclock(0, -2000))
        self.assertFalse(package.set_gpu_overclock(0, 3000))
        self.assertFalse(package.set_gpu_overclock("invalid", "offset"))

        # Test safe ranges
        self.assertTrue(package.set_gpu_overclock(50, 100))
        oc = monitor.get_overclock_settings()
        self.assertEqual(oc["core_offset"], 50)
        self.assertEqual(oc["mem_offset"], 100)
        self.assertTrue(oc["is_active"])

        # Reset
        self.assertTrue(package.set_gpu_overclock(0, 0))

    def test_timeshift_helpers_and_package_whitelisting(self):
        import monitor
        self.assertIsInstance(monitor.is_timeshift_installed(), bool)
        self.assertTrue(package._is_allowed_package("mangohud"))
        self.assertTrue(package._is_allowed_package("timeshift"))
        self.assertTrue(package._is_allowed_package("goverlay"))

    def test_tray_module_initialization(self):
        import tray
        ind = tray.run_tray_indicator()
        self.assertIsNotNone(ind)
        self.assertTrue(hasattr(ind, "menu"))


class TestMetadataAndFiles(unittest.TestCase):
    def test_desktop_file_syntax(self):
        desktop_file = os.path.join(PROJECT_DIR, "org.parslinux.nvidia-installer.desktop")
        self.assertTrue(os.path.isfile(desktop_file))
        with open(desktop_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("[Desktop Entry]", content)
        self.assertIn("Name=ParsLinux Nvidia Installer", content)
        self.assertIn("Exec=parslinux-nvidia-installer", content)
        self.assertIn("Icon=parslinux-nvidia-installer", content)

    def test_polkit_policy_syntax(self):
        policy_file = os.path.join(PROJECT_DIR, "org.parslinux.pkexec.parslinux-nvidia-installer.policy")
        self.assertTrue(os.path.isfile(policy_file))
        tree = ET.parse(policy_file)
        root = tree.getroot()
        self.assertEqual(root.tag, "policyconfig")
        action_ids = [a.attrib.get("id") for a in root.findall("action")]
        self.assertIn("org.parslinux.pkexec.parslinux-nvidia-installer", action_ids)

    def test_metainfo_xml_syntax(self):
        metainfo_file = os.path.join(PROJECT_DIR, "data/org.parslinux.nvidia-installer.metainfo.xml")
        self.assertTrue(os.path.isfile(metainfo_file))
        tree = ET.parse(metainfo_file)
        root = tree.getroot()
        self.assertEqual(root.tag, "component")
        self.assertEqual(root.find("id").text, "org.parslinux.nvidia-installer")

    def test_glade_ui_files_valid_xml(self):
        for glade in ("ui/ui.glade", "ui/driver_toggle.glade"):
            path = os.path.join(PROJECT_DIR, glade)
            self.assertTrue(os.path.isfile(path))
            tree = ET.parse(path)
            self.assertEqual(tree.getroot().tag, "interface")

    def test_gtk4_ui_validation(self):
        import subprocess
        for glade in ("ui/ui.glade", "ui/driver_toggle.glade"):
            path = os.path.join(PROJECT_DIR, glade)
            res = subprocess.run(["gtk4-builder-tool", "validate", path], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"GTK4 validation failed for {glade}: {res.stderr}")

    def test_gtk4_app_launch_simulated(self):
        import subprocess
        cmd = [
            sys.executable,
            "-c",
            "import os, sys; sys.path.insert(0, 'src'); os.environ['PARSLINUX_NVI_DEBUG']='1'; import Main, MainWindow; app = Main.Application(); win = MainWindow.MainWindow(app); sys.exit(0 if win.ui_main_window is not None else 1)"
        ]
        res = subprocess.run(cmd, cwd=PROJECT_DIR, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"GTK4 application failed to launch: {res.stderr}")


class TestAutoDetectionSystem(unittest.TestCase):
    def test_detect_all_system_gpus(self):
        import detector
        gpus = detector.detect_all_system_gpus()
        self.assertIsInstance(gpus, list)
        self.assertGreater(len(gpus), 0)
        gpu = gpus[0]
        self.assertIn("pci_slot", gpu)
        self.assertIn("vendor_id", gpu)
        self.assertIn("device_id", gpu)
        self.assertIn("device_name", gpu)
        self.assertIn("is_primary", gpu)
        self.assertIn("is_nvidia", gpu)

    def test_identify_architectures(self):
        import detector
        # Blackwell
        arch, _, pkg, _ = detector.identify_architecture(0x2900, "GeForce RTX 5090")
        self.assertEqual(arch, "Blackwell")
        self.assertEqual(pkg, "nvidia-driver")

        # Ada Lovelace
        arch, _, pkg, _ = detector.identify_architecture(0x2782, "GeForce RTX 4070 Ti")
        self.assertEqual(arch, "Ada Lovelace")
        self.assertEqual(pkg, "nvidia-driver")

        # Ampere
        arch, _, pkg, _ = detector.identify_architecture(0x2503, "GeForce RTX 3060")
        self.assertEqual(arch, "Ampere")
        self.assertEqual(pkg, "nvidia-driver")

        # Turing
        arch, _, pkg, _ = detector.identify_architecture(0x2184, "GeForce GTX 1660")
        self.assertEqual(arch, "Turing")
        self.assertEqual(pkg, "nvidia-driver")

        # Pascal
        arch, _, pkg, _ = detector.identify_architecture(0x1B81, "GeForce GTX 1070")
        self.assertEqual(arch, "Pascal")
        self.assertEqual(pkg, "nvidia-driver")

        # Kepler (Legacy 470)
        arch, _, pkg, _ = detector.identify_architecture(0x1187, "GeForce GTX 760")
        self.assertEqual(arch, "Kepler")
        self.assertEqual(pkg, "nvidia-tesla-470-driver")

        # Fermi (Legacy 390)
        arch, _, pkg, _ = detector.identify_architecture(0x0DC4, "GeForce GTS 450")
        self.assertEqual(arch, "Fermi")
        self.assertEqual(pkg, "nvidia-legacy-390xx-driver")

    def test_driver_tag_recommendation(self):
        import detector
        drivers_list = [
            nvidia.NvidiaDriver("xserver-xorg-video-nouveau", "1.0.17", "Open Source", "Debian", False),
            nvidia.NvidiaDriver("nvidia-driver", "550.120", "Proprietary", "NVIDIA", False),
            nvidia.NvidiaDriver("nvidia-tesla-470-driver", "470.256", "Legacy", "Debian", False),
        ]
        # Simulate an Ampere GPU
        dev = nvidia.NvidiaDevice(
            vendor_id=0x10DE,
            vendor_name="NVIDIA Corporation",
            device_id=0x2503,
            device_name="GeForce RTX 3060",
            architecture="Ampere",
            recommended_driver="nvidia-driver",
            recommendation_reason="Ampere mimarisi için önerilmektedir",
        )
        rec = detector.tag_recommended_driver(drivers_list, [dev])
        self.assertIsNotNone(rec)
        self.assertEqual(rec.package, "nvidia-driver")
        self.assertTrue(rec.is_recommended)
        self.assertIn("Ampere", rec.recommendation_reason)

    def test_kepler_driver_tag_recommendation(self):
        import detector
        drivers_list = [
            nvidia.NvidiaDriver("xserver-xorg-video-nouveau", "1.0.17", "Open Source", "Debian", False),
            nvidia.NvidiaDriver("nvidia-driver", "550.120", "Proprietary", "NVIDIA", False),
            nvidia.NvidiaDriver("nvidia-tesla-470-driver", "470.256", "Legacy", "Debian", False),
        ]
        # Simulate a Kepler GPU
        dev = nvidia.NvidiaDevice(
            vendor_id=0x10DE,
            vendor_name="NVIDIA Corporation",
            device_id=0x1187,
            device_name="GeForce GTX 760",
            architecture="Kepler",
            recommended_driver="nvidia-tesla-470-driver",
            recommendation_reason="Kepler mimarisi için 470 sürücüsü önerilmektedir",
        )
        rec = detector.tag_recommended_driver(drivers_list, [dev])
        self.assertIsNotNone(rec)
        self.assertEqual(rec.package, "nvidia-tesla-470-driver")
        self.assertTrue(rec.is_recommended)

    def test_hardware_report(self):
        import detector
        report = detector.generate_hardware_report()
        self.assertIn("ParsLinux Donanım & GPU Otomatik Algılama Raporu", report)
        self.assertIn("GPU #1", report)

    def test_nvidia_module_recommendation_integration(self):
        os.environ["PARSLINUX_NVI_DEBUG"] = "1"
        try:
            gpus = nvidia.graphics()
            self.assertGreater(len(gpus), 0)
            gpu = gpus[0]
            self.assertIsNotNone(gpu.architecture)
            self.assertIsNotNone(gpu.recommended_driver)

            drvs = nvidia.drivers(gpus)
            recommended_drvs = [d for d in drvs if getattr(d, "is_recommended", False)]
            self.assertEqual(len(recommended_drvs), 1)
            self.assertEqual(recommended_drvs[0].package, "nvidia-driver")
        finally:
            os.environ.pop("PARSLINUX_NVI_DEBUG", None)


if __name__ == "__main__":
    unittest.main()

