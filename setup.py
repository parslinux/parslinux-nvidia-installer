#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ParsLinux Nvidia Installer - Setup Script
"""

import os
import subprocess
from setuptools import setup, find_packages


def create_mo_files():
    podir = "data/po"
    mo = []
    if os.path.exists(podir):
        for po in os.listdir(podir):
            if po.endswith(".po"):
                lang = po.split(".po")[0]
                lang_dir = f"mo/{lang}/LC_MESSAGES"
                os.makedirs(lang_dir, exist_ok=True)
                mo_file = f"{lang_dir}/parslinux-nvidia-installer.mo"
                msgfmt_cmd = f"msgfmt {podir}/{po} -o {mo_file}"
                subprocess.call(msgfmt_cmd, shell=True)
                mo.append((f"/usr/share/locale/{lang}/LC_MESSAGES", [mo_file]))
    return mo


version = "1.0.0"
ver_path = "src/__version__"
if os.path.exists(ver_path):
    try:
        with open(ver_path) as f:
            version = f.read().strip()
    except Exception:
        pass

icon_source = "images/parslinux-nvidia-installer.svg" if os.path.isfile("images/parslinux-nvidia-installer.svg") else "parslinux-nvidia-installer.svg"

data_files = [
    ("/usr/share/applications", ["org.parslinux.nvidia-installer.desktop"]),
    ("/usr/share/metainfo", ["data/org.parslinux.nvidia-installer.metainfo.xml"]),
    ("/usr/share/polkit-1/actions", ["org.parslinux.pkexec.parslinux-nvidia-installer.policy"]),
    ("/usr/share/icons/hicolor/scalable/apps", [icon_source]),
    ("/usr/bin", ["parslinux-nvidia-installer"]),
    ("/usr/share/parslinux/parslinux-nvidia-installer", [
        "parslinux-nvidia-installer",
        icon_source,
        "pni-disable-gpu.sh",
        "nvidia.pub",
        "update_translations.sh"
    ]),
    ("/usr/share/parslinux/parslinux-nvidia-installer/images", [
        "images/parslinux-nvidia-installer.svg"
    ]),
    ("/usr/share/parslinux/parslinux-nvidia-installer/src", [
        "src/Main.py",
        "src/MainWindow.py",
        "src/detector.py",
        "src/monitor.py",
        "src/tray.py",
        "src/nvidia.py",
        "src/package.py",
        "src/__version__"
    ]),
    ("/usr/share/parslinux/parslinux-nvidia-installer/ui", [
        "ui/ui.glade",
        "ui/driver_toggle.glade"
    ]),
    ("/usr/share/parslinux/parslinux-nvidia-installer/data", [
        "data/nvidia-pci.json",
        "data/style.css"
    ]),
    ("/usr/share/parslinux/parslinux-nvidia-installer/data/assets", [
        "data/assets/nouveau_logo.png",
        "data/assets/nvidia_logo.png",
        "data/assets/nvidia_logo.svg",
        "data/assets/parslinux-logo.svg",
        "data/assets/video_card.svg",
        "data/assets/video_card_disabled.svg"
    ]),
    ("/lib/systemd/system", ["pni-disable-gpu.service"]),
] + create_mo_files()

setup(
    name="parslinux-nvidia-installer",
    version=version,
    packages=find_packages(),
    scripts=["parslinux-nvidia-installer"],
    data_files=data_files,
    author="ParsLinux Developers",
    author_email="dev@parslinux.org",
    description="ParsLinux NVIDIA Graphics Driver Installer & GPU Manager",
    long_description=open("README.md").read() if os.path.isfile("README.md") else "",
    long_description_content_type="text/markdown",
    license="GPLv3",
    keywords="nvidia driver graphics installer parslinux cuda hybrid",
    url="https://parslinux.org",
)
