#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ParsLinux Nvidia Installer - Automated Screenshot Generator
Renders native high-resolution GTK4 screenshots of all application tabs.
"""

import os
import sys

# Ensure project root & src are on path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, "src"))
os.chdir(project_root)
os.environ["PARSLINUX_NVI_DEBUG"] = "1"

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from MainWindow import MainWindow


def capture_window(window, filepath):
    width = window.get_width()
    height = window.get_height()
    paintable = Gtk.WidgetPaintable.new(window)
    snapshot = Gtk.Snapshot.new()
    paintable.snapshot(snapshot, float(width), float(height))
    node = snapshot.to_node()
    native = window.get_native()
    renderer = native.get_renderer()
    texture = renderer.render_texture(node, None)
    return texture.save_to_png(filepath)


def process_events():
    ctx = GLib.MainContext.default()
    for _ in range(50):
        ctx.iteration(False)


def run_generator():
    app = Gtk.Application(application_id="org.parslinux.nvidia-installer.shotgen")

    def on_activate(app):
        images_dir = os.path.join(project_root, "images")
        os.makedirs(images_dir, exist_ok=True)

        mw = MainWindow(app)
        win = mw.ui_main_window
        win.present()
        mw.feature_stack.set_transition_type(Gtk.StackTransitionType.NONE)

        process_events()

        tabs = [
            ("drivers", "screenshot_drivers.png"),
            ("monitor", "screenshot_monitor.png"),
            ("gaming", "screenshot_gaming.png"),
            ("ai_tools", "screenshot_ai.png"),
        ]

        for tab_name, filename in tabs:
            mw.feature_stack.set_visible_child_name(tab_name)
            process_events()
            target_path = os.path.join(images_dir, filename)
            success = capture_window(win, target_path)
            print(f"[✓] Captured {tab_name} -> {target_path} (Success: {success})")

        # Save monitor tab as main hero screenshot
        mw.feature_stack.set_visible_child_name("monitor")
        process_events()
        main_screenshot = os.path.join(images_dir, "screenshot.png")
        capture_window(win, main_screenshot)
        print(f"[✓] Saved default screenshot -> {main_screenshot}")

        app.quit()

    app.connect("activate", on_activate)
    return app.run(None)


if __name__ == "__main__":
    sys.exit(run_generator())
