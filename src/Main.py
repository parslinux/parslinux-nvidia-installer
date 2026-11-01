#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ParsLinux Nvidia Installer - Application Entry Point
"""

import gi
import sys
import os

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GLib

from MainWindow import MainWindow


class Application(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            application_id="org.parslinux.nvidia-installer",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE | Gio.ApplicationFlags.NON_UNIQUE,
            **kwargs
        )
        self.window = None
        self.args = {}

        self.add_main_option(
            "details",
            ord("d"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Show details view of graphics hardware and drivers",
            None,
        )

        self.add_main_option(
            "detect",
            ord("c"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Auto-detect graphics hardware and display diagnostic report",
            None,
        )

        self.add_main_option(
            "json",
            ord("j"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Output hardware detection report in JSON format",
            None,
        )

        self.add_main_option(
            "remove",
            ord("r"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Open removal/purge page of proprietary drivers",
            None,
        )

        self.add_main_option(
            "debug",
            ord("g"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Enable debug and simulated hardware mode",
            None,
        )

        self.add_main_option(
            "tray",
            ord("t"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Run background system tray indicator for temperature & profile monitoring",
            None,
        )

        self.add_main_option(
            "version",
            ord("v"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Show version information and exit",
            None,
        )

    def do_activate(self):
        if not self.window:
            self.window = MainWindow(self)
        if self.window and self.window.ui_main_window:
            self.window.ui_main_window.present()

    def do_command_line(self, command_line):
        options = command_line.get_options_dict()
        self.args = options.end().unpack()

        if "version" in self.args:
            ver_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "__version__")
            version = "1.0.0"
            if os.path.isfile(ver_file):
                try:
                    with open(ver_file) as f:
                        version = f.read().strip()
                except Exception:
                    pass
            print(f"ParsLinux Nvidia Installer {version}")
            return 0

        if "debug" in self.args:
            os.environ["PARSLINUX_NVI_DEBUG"] = "1"

        if "detect" in self.args or "details" in self.args:
            import detector
            import json as json_mod
            if "json" in self.args:
                gpus = detector.detect_all_system_gpus()
                print(json_mod.dumps(gpus, indent=2, ensure_ascii=False))
            else:
                print(detector.generate_hardware_report())
            return 0

        if "tray" in self.args:
            import subprocess
            tray_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tray.py")
            subprocess.Popen([sys.executable, tray_script])
            return 0

        self.activate()
        return 0


app = Application()

def main():
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
