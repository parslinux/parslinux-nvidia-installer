#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ParsLinux Nvidia Installer - System Tray & AppIndicator Module
Provides background GPU temperature monitoring and quick PRIME profile switching in the system tray.
"""

import os
import sys
import subprocess
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

HAS_INDICATOR = False
Indicator = None

# Try loading AppIndicator3 or AyatanaAppIndicator3
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as IndicatorLib
    HAS_INDICATOR = True
except Exception:
    try:
        gi.require_version("AppIndicator3", "0.1")
        from gi.repository import AppIndicator3 as IndicatorLib
        HAS_INDICATOR = True
    except Exception:
        IndicatorLib = None

import monitor
import package

TRAY_ID = "parslinux-nvidia-tray"


class NvidiaTrayIndicator:
    def __init__(self, on_open_callback=None):
        self.on_open_callback = on_open_callback
        self.indicator = None
        self.status_icon = None

        icon_name = "parslinux-nvidia-installer"

        if HAS_INDICATOR and IndicatorLib:
            self.indicator = IndicatorLib.Indicator.new(
                TRAY_ID,
                icon_name,
                IndicatorLib.IndicatorCategory.HARDWARE,
            )
            self.indicator.set_status(IndicatorLib.IndicatorStatus.ACTIVE)
            self.menu = Gtk.Menu()
            self.build_menu()
            self.indicator.set_menu(self.menu)
        else:
            # Fallback to standard Gtk.StatusIcon
            try:
                self.status_icon = Gtk.StatusIcon.new_from_icon_name(icon_name)
                self.status_icon.set_title("ParsLinux Nvidia")
                self.menu = Gtk.Menu()
                self.build_menu()
                self.status_icon.connect("popup-menu", self.on_status_icon_popup)
                self.status_icon.connect("activate", self.on_open_window)
            except Exception as e:
                print(f"Warning: Failed to create Gtk.StatusIcon: {e}", file=sys.stderr)

        self.update_tray()
        GLib.timeout_add_seconds(3, self.update_tray)

    def on_status_icon_popup(self, icon, button, activate_time):
        self.menu.popup(None, None, Gtk.StatusIcon.position_menu, icon, button, activate_time)

    def build_menu(self):
        # Header / Title
        self.item_title = Gtk.MenuItem(label="ParsLinux Nvidia Control")
        self.item_title.set_sensitive(False)
        self.menu.append(self.item_title)

        # GPU Temp & Status Info
        self.item_temp = Gtk.MenuItem(label="🌡️ GPU: Taranıyor...")
        self.item_temp.set_sensitive(False)
        self.menu.append(self.item_temp)

        self.item_mode = Gtk.MenuItem(label="⚡ Profil: Taranıyor...")
        self.item_mode.set_sensitive(False)
        self.menu.append(self.item_mode)

        self.menu.append(Gtk.SeparatorMenuItem())

        # Profile Switchers
        item_integ = Gtk.MenuItem(label="🍃 Tasarruf Modu (Entegre GPU)")
        item_integ.connect("activate", lambda w: self.switch_profile("integrated"))
        self.menu.append(item_integ)

        item_ondemand = Gtk.MenuItem(label="⚡ Hibrit Mod (İsteğe Bağlı)")
        item_ondemand.connect("activate", lambda w: self.switch_profile("on-demand"))
        self.menu.append(item_ondemand)

        item_nvidia = Gtk.MenuItem(label="🚀 Performans Modu (NVIDIA)")
        item_nvidia.connect("activate", lambda w: self.switch_profile("nvidia"))
        self.menu.append(item_nvidia)

        self.menu.append(Gtk.SeparatorMenuItem())

        # Open Control Panel
        item_open = Gtk.MenuItem(label="🖥️ Kontrol Panelini Aç")
        item_open.connect("activate", self.on_open_window)
        self.menu.append(item_open)

        # Quit
        item_quit = Gtk.MenuItem(label="🚪 Kapat")
        item_quit.connect("activate", lambda w: Gtk.main_quit())
        self.menu.append(item_quit)

        self.menu.show_all()

    def update_tray(self):
        is_debug = os.environ.get("PARSLINUX_NVI_DEBUG") == "1"
        data = monitor.get_gpu_telemetry(simulated=is_debug)
        prime_mode = monitor.get_prime_profile()

        mode_names = {
            "integrated": "Tasarruf (Entegre)",
            "on-demand": "Hibrit",
            "nvidia": "Performans",
        }
        mode_text = mode_names.get(prime_mode, prime_mode)

        if data and data.get("available"):
            temp = data.get("temp", 45)
            gpu_name = data.get("name", "NVIDIA GPU")
            power = data.get("power", 0)

            label_text = f"{temp}°C • {mode_text}"
            if self.indicator:
                self.indicator.set_label(label_text, "100°C • Performans")

            self.item_temp.set_label(f"🌡️ {gpu_name}: {temp}°C ({power}W)")
            self.item_mode.set_label(f"⚡ Aktif Profil: {mode_text}")
        else:
            if self.indicator:
                self.indicator.set_label(mode_text, "Performans")
            self.item_mode.set_label(f"⚡ Aktif Profil: {mode_text}")

        return True

    def switch_profile(self, mode):
        cmd = ["pkexec", "/usr/share/parslinux/parslinux-nvidia-installer/src/package.py", "prime-mode", mode]
        try:
            subprocess.Popen(cmd)
        except Exception as e:
            print(f"Failed to switch profile: {e}", file=sys.stderr)

    def on_open_window(self, widget):
        if self.on_open_callback:
            self.on_open_callback()
        else:
            try:
                subprocess.Popen(["parslinux-nvidia-installer"])
            except Exception:
                pass


def run_tray_indicator(on_open_callback=None):
    indicator = NvidiaTrayIndicator(on_open_callback)
    return indicator


def main():
    ind = run_tray_indicator()
    loop = GLib.MainLoop()
    loop.run()


if __name__ == "__main__":
    main()
