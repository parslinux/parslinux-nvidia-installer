#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ParsLinux Nvidia Installer - Main Window Controller
"""

import gi
import os
import signal
import subprocess
import sys
import shutil
import locale
import platform

import detector
import monitor
import nvidia
import package

gi.require_version("Gtk", "4.0")
gi.require_version("Polkit", "1.0")
gi.require_version("Vte", "3.91")

from gi.repository import Gtk, GObject, GLib, Vte, Gdk, GdkPixbuf
from locale import gettext as _

# GTK4 Box / ScrolledWindow / Widget compatibility helpers
if not hasattr(Gtk.Box, "pack_start"):
    def _box_pack_start(self, child, expand=False, fill=False, padding=0):
        if expand:
            if self.get_orientation() == Gtk.Orientation.HORIZONTAL:
                child.set_hexpand(True)
            else:
                child.set_vexpand(True)
        self.append(child)
    Gtk.Box.pack_start = _box_pack_start

if not hasattr(Gtk.Box, "pack_end"):
    def _box_pack_end(self, child, expand=False, fill=False, padding=0):
        if expand:
            if self.get_orientation() == Gtk.Orientation.HORIZONTAL:
                child.set_hexpand(True)
            else:
                child.set_vexpand(True)
        self.append(child)
    Gtk.Box.pack_end = _box_pack_end

if not hasattr(Gtk.Box, "reorder_child"):
    def _box_reorder_child(self, child, position):
        if position <= 0:
            self.reorder_child_after(child, None)
        else:
            cur = self.get_first_child()
            idx = 0
            sibling = None
            while cur:
                if cur != child:
                    if idx == position - 1:
                        sibling = cur
                        break
                    idx += 1
                cur = cur.get_next_sibling()
            self.reorder_child_after(child, sibling)
    Gtk.Box.reorder_child = _box_reorder_child

if not hasattr(Gtk.ScrolledWindow, "add"):
    Gtk.ScrolledWindow.add = lambda self, child: self.set_child(child)

if hasattr(Gtk, "CenterBox") and not hasattr(Gtk.CenterBox, "pack_start"):
    Gtk.CenterBox.pack_start = lambda self, child, expand=False, fill=False, padding=0: self.set_center_widget(child)

if not hasattr(Gtk.Label, "set_line_wrap"):
    Gtk.Label.set_line_wrap = lambda self, wrap: self.set_wrap(wrap)

if not hasattr(Gtk.Widget, "show_all"):
    Gtk.Widget.show_all = lambda self: self.set_visible(True)

APPNAME_CODE = "parslinux-nvidia-installer"
TRANSLATIONS_PATH = "/usr/share/locale/"
locale.bindtextdomain(APPNAME_CODE, TRANSLATIONS_PATH)
locale.bindtextdomain("pardus-nvidia-installer", TRANSLATIONS_PATH)
locale.textdomain(APPNAME_CODE)

act_id = "org.parslinux.pkexec.parslinux-nvidia-installer"
socket_path = "/tmp/parslinux-nvidia-installer"
nouveau = "xserver-xorg-video-nouveau"
driver_packages = {
    "nouveau": "xserver-xorg-video-nouveau",
    "current": "nvidia-driver",
    470: "nvidia-tesla-470-driver",
}
pkg_opr = {"purge": ""}

cur_path = os.path.dirname(os.path.abspath(__file__))


def get_package_exec_path():
    system_path = "/usr/share/parslinux/parslinux-nvidia-installer/src/package.py"
    if os.path.isfile(system_path):
        return system_path
    local_path = os.path.join(cur_path, "package.py")
    if os.path.isfile(local_path):
        return local_path
    return "/usr/share/pardus/pardus-nvidia-installer/src/package.py"


def check_is_reboot_pending():
    return (
        os.path.isfile("/run/parslinux-nvi.reboot")
        or os.path.isfile("/run/pardus-nvi.reboot")
    )


def get_system_gpu_description():
    try:
        gpus = detector.detect_all_system_gpus()
        if gpus:
            desc_items = []
            for g in gpus:
                role = _("Birincil") if g.get("is_primary") else _("Harici/İkincil")
                desc_items.append(f"{g.get('device_name')} ({role})")
            return " + ".join(desc_items)
    except Exception:
        pass
    return _("Intel / AMD Grafik Bağdaştırıcısı")


def apply_custom_css():
    try:
        css_provider = Gtk.CssProvider()
        css_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "../data/style.css"))
        if os.path.isfile(css_path):
            css_provider.load_from_path(css_path)
            display = Gdk.Display.get_default()
            if display:
                Gtk.StyleContext.add_provider_for_display(
                    display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
    except Exception as e:
        print(f"Warning: Failed to load style.css: {e}", file=sys.stderr)


class MainWindow(object):
    @staticmethod
    def _build_ui_file(file_path):
        assets_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "../data/assets"))
        if not os.path.isdir(assets_dir):
            assets_dir = "/usr/share/parslinux/parslinux-nvidia-installer/data/assets"
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            content = content.replace("../data/assets", assets_dir)
            return Gtk.Builder.new_from_string(content, len(content.encode("utf-8")))
        except Exception as e:
            print(f"Failed to load UI from {file_path}: {e}", file=sys.stderr)
            sys.exit(1)

    def __init__(self, application):
        self.application = application
        self.ui_interface_file = os.path.join(os.path.dirname(__file__), "../ui/ui.glade")
        self.gtk_builder = self._build_ui_file(self.ui_interface_file)

        apply_custom_css()

        self.is_debug = nvidia.is_debug_mode()

        self.ui_confirm_dialog = self.get_ui("ui_confirm_dialog")
        self.get_ui("ui_button_reboot_dlg").connect("clicked", self.do_reboot)
        self.get_ui("ui_button_exit_dlg").connect(
            "clicked", lambda x: self.application.quit()
        )

        if check_is_reboot_pending():
            self.ui_main_window = self.get_ui("ui_window_reboot")
            self.ui_main_window.set_application(application)
            self.ui_main_window.present()
            return

        self.driver_buttons = []
        self.active_driver = ""
        self.toggled_driver = None
        self.drv_arr = []
        self.gpu_info_arr = []
        self.initial_gpu_driver = None
        self.initial_sec_gpu_state = False
        self.state = nvidia.source()

        self.ui_gpu_info_box = self.get_ui("ui_gpu_info_box")
        self.ui_gpu_box = self.get_ui("ui_gpu_box")
        self.ui_drv_box = self.get_ui("ui_drv_box")
        self.ui_main_box = self.get_ui("ui_main_box")
        self.ui_main_window = self.get_ui("ui_main_window")

        self.ui_info_stack = self.get_ui("ui_info_stack")
        self.ui_disabled_gpu_box = self.get_ui("ui_disabled_gpu_box")
        self.ui_enabled_gpu_box = self.get_ui("ui_enabled_gpu_box")

        self.ui_apply_chg_button = self.get_ui("ui_apply_chg_button")
        self.ui_disable_check_button = self.get_ui("ui_disable_check_button")

        self.ui_apply_chg_button.connect("clicked", self.on_apply_button_clicked)
        self.ui_repo_switch = self.get_ui("ui_repo_switch")
        self.ui_repo_switch.set_state(self.state)
        self.mirror_handler_id = self.ui_repo_switch.connect(
            "state-set", self.on_nvidia_mirror_changed
        )

        self.ui_about_dialog = self.get_ui("ui_about_dialog")
        self.ui_about_button = self.get_ui("ui_about_button")

        # Set version from __version__ file
        version = "1.0.0"
        try:
            ver_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "__version__")
            if os.path.isfile(ver_path):
                version = open(ver_path).readline().strip()
        except Exception:
            pass
        # Configure icon search path so named icons resolve locally
        display = Gdk.Display.get_default()
        if display:
            icon_theme = Gtk.IconTheme.get_for_display(display)
            if icon_theme:
                icon_theme.add_search_path(os.path.normpath(os.path.join(os.path.dirname(__file__), "../images")))
                icon_theme.add_search_path(os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))
                icon_theme.add_search_path(os.path.normpath(os.path.join(os.path.dirname(__file__), "../data/assets")))

        # Load ParsLinux logo pixbuf directly
        logo_paths = [
            os.path.normpath(os.path.join(os.path.dirname(__file__), "../images/parslinux-nvidia-installer.svg")),
            os.path.normpath(os.path.join(os.path.dirname(__file__), "../parslinux-nvidia-installer.svg")),
            os.path.normpath(os.path.join(os.path.dirname(__file__), "../data/assets/parslinux-logo.svg")),
            "/usr/share/icons/hicolor/scalable/apps/parslinux-nvidia-installer.svg",
        ]
        self.app_icon_pixbuf = None
        for lp in logo_paths:
            if os.path.isfile(lp):
                try:
                    self.app_icon_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(lp, 128, 128, True)
                    break
                except Exception:
                    pass

        if self.ui_about_dialog:
            self.ui_about_dialog.set_version(version)
            self.ui_about_dialog.set_program_name("ParsLinux Nvidia Installer")
            self.ui_about_dialog.set_website("https://parslinux.org")
            if self.app_icon_pixbuf and hasattr(self.ui_about_dialog, "set_logo"):
                try:
                    self.ui_about_dialog.set_logo(self.app_icon_pixbuf)
                except Exception:
                    pass

        if self.ui_main_window:
            self.ui_main_window.set_icon_name("parslinux-nvidia-installer")

        self.ui_info_dialog = self.get_ui("ui_info_dialog")
        self.ui_about_button.connect("clicked", self.on_about_button_clicked)

        self.nvidia_devices = nvidia.graphics()
        self.ui_controller_box = self.get_ui("ui_controller_box")
        self.ui_secondary_gpu_box = self.get_ui("ui_secondary_gpu_box")

        self.ui_main_stack = self.get_ui("ui_main_stack")
        self.ui_nvidia_box = self.get_ui("ui_nvidia_box")
        self.ui_novidia_box = self.get_ui("ui_novidia_box")
        self.ui_disable_check_button.connect(
            "toggled", self.on_disable_checkbox_checked
        )
        self.ui_enable_button = self.get_ui("ui_enable_button")
        self.ui_enable_button.connect("clicked", self.on_enable_button_clicked)

        # Simulation button in no-device view
        self.ui_btn_simulate = self.get_ui("ui_btn_simulate")
        if self.ui_btn_simulate:
            self.ui_btn_simulate.connect("clicked", self.on_simulate_clicked)

        # Build dynamic hardware auto-detection toolbar in no-nvidia page
        if self.ui_novidia_box:
            novidia_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            novidia_btn_box.set_halign(Gtk.Align.CENTER)

            btn_rescan_novidia = Gtk.Button.new_with_label(_("🔄 Donanımı Yeniden Tara"))
            btn_rescan_novidia.get_style_context().add_class("rescan-btn")
            btn_rescan_novidia.connect("clicked", lambda b: self.on_rescan_hardware())
            novidia_btn_box.pack_start(btn_rescan_novidia, False, False, 0)

            btn_diag_novidia = Gtk.Button.new_with_label(_("🔍 Donanım Raporunu Görüntüle"))
            btn_diag_novidia.get_style_context().add_class("diag-btn")
            btn_diag_novidia.connect("clicked", lambda b: self.on_show_hardware_diagnostics())
            novidia_btn_box.pack_start(btn_diag_novidia, False, False, 0)

            self.ui_novidia_box.pack_start(novidia_btn_box, False, False, 4)

            # Architecture test presets
            lbl_sim_presets = Gtk.Label()
            lbl_sim_presets.set_markup('<span font_size="small" foreground="#64748B"><b>Otomatik Algılama Simülatörü:</b></span>')
            self.ui_novidia_box.pack_start(lbl_sim_presets, False, False, 2)

            preset_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            preset_box.set_halign(Gtk.Align.CENTER)

            btn_ada = Gtk.Button.new_with_label("RTX 4070 Ti (Ada)")
            btn_ada.connect("clicked", lambda b: self.on_simulate_custom_gpu("ada"))
            preset_box.pack_start(btn_ada, False, False, 0)

            btn_amp = Gtk.Button.new_with_label("RTX 3060 (Ampere)")
            btn_amp.connect("clicked", lambda b: self.on_simulate_custom_gpu("ampere"))
            preset_box.pack_start(btn_amp, False, False, 0)

            btn_kep = Gtk.Button.new_with_label("GTX 760 (Kepler Legacy)")
            btn_kep.connect("clicked", lambda b: self.on_simulate_custom_gpu("kepler"))
            preset_box.pack_start(btn_kep, False, False, 0)

            self.ui_novidia_box.pack_start(preset_box, False, False, 4)

        self.ui_detected_gpu_label = self.get_ui("ui_detected_gpu_label")
        if self.ui_detected_gpu_label:
            detected = get_system_gpu_description()
            self.ui_detected_gpu_label.set_markup(
                f'<span foreground="#94A3B8"><b>Sistemdeki Donanım:</b> {detected}</span>'
            )

        marker_present = not package.check_sec_state()
        self.disabled_no_devices = (
            not self.nvidia_devices and marker_present and not self.is_debug
        )

        self.check_secondary_gpu()

        self.apt_opr = ""
        if self.disabled_no_devices:
            self.ui_main_stack.set_visible_child(self.ui_nvidia_box)
            self.ui_apply_chg_button.set_sensitive(False)
            self.ui_repo_switch.set_sensitive(False)
        else:
            self.create_gpu_drivers()

        self.vte = Vte.Terminal()
        self.update_vte_color(self.vte)
        self.ui_box_vte = self.get_ui("ui_box_vte")
        vte_scrolled = Gtk.ScrolledWindow()
        vte_scrolled.set_child(self.vte)
        if hasattr(self.ui_box_vte, "set_center_widget"):
            self.ui_box_vte.set_center_widget(vte_scrolled)
        else:
            self.ui_box_vte.pack_start(vte_scrolled, True, True, 0)
        self.vte.connect("child-exited", self.on_vte_done)

        self.get_ui("ui_button_reboot").connect("clicked", self.do_reboot)
        self.get_ui("ui_button_exit").connect(
            "clicked", lambda x: self.application.quit()
        )

        self.op_widgets = (
            self.ui_apply_chg_button,
            self.ui_repo_switch,
            self.ui_enable_button,
            self.ui_disable_check_button,
        )

        self.setup_feature_tabs()
        GLib.timeout_add_seconds(2, self.refresh_telemetry_ui)

        self.ui_main_window.set_default_size(580, 720)
        self.ui_main_window.set_application(application)
        self.ui_main_window.set_title(_("ParsLinux Nvidia Installer"))

        # Add HeaderBar action buttons
        headerbar = self.ui_main_window.get_titlebar()
        if headerbar and isinstance(headerbar, Gtk.HeaderBar):
            self.btn_header_rescan = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
            self.btn_header_rescan.set_tooltip_text(_("Donanımı Yeniden Tara (Rescan GPUs)"))
            self.btn_header_rescan.connect("clicked", lambda b: self.on_rescan_hardware())
            headerbar.pack_start(self.btn_header_rescan)

            self.btn_header_diag = Gtk.Button.new_from_icon_name("dialog-information-symbolic")
            self.btn_header_diag.set_tooltip_text(_("Donanım Raporu & Tanılama"))
            self.btn_header_diag.connect("clicked", lambda b: self.on_show_hardware_diagnostics())
            headerbar.pack_start(self.btn_header_diag)

            self.btn_header_snapshot = Gtk.Button.new_from_icon_name("document-save-symbolic")
            self.btn_header_snapshot.set_tooltip_text(_("Sistem Geri Yükleme Noktası Al (Timeshift)"))
            self.btn_header_snapshot.connect("clicked", lambda b: self.on_create_snapshot_clicked())
            headerbar.pack_start(self.btn_header_snapshot)

            self.btn_tray_toggle = Gtk.Button.new_from_icon_name("media-record-symbolic")
            self.btn_tray_toggle.set_tooltip_text(_("Sistem Tepsisi Göstergesini Başlat (Tray)"))
            self.btn_tray_toggle.connect("clicked", lambda b: self.start_tray_indicator())
            headerbar.pack_end(self.btn_tray_toggle)

        self.ui_main_window.present()

    def on_simulate_clicked(self, button):
        self.on_simulate_custom_gpu("ampere")

    def do_reboot(self, widget):
        root = widget.get_root() if hasattr(widget, "get_root") else self.ui_main_window
        dialog = Gtk.MessageDialog(
            transient_for=root if isinstance(root, Gtk.Window) else None,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=_("Warning"),
        )
        dialog.set_use_markup(True)
        dialog.format_secondary_text(
            _("Changes have been made. To ensure these changes take effect, a system restart is required. Please save any work and click 'OK' to complete the process.")
        )
        def _on_reboot_response(dlg, response_id):
            dlg.destroy()
            if response_id == Gtk.ResponseType.OK:
                cmd = [
                    "/usr/bin/dbus-send",
                    "--system",
                    "--print-reply",
                    "--dest=org.freedesktop.login1",
                    "/org/freedesktop/login1",
                    "org.freedesktop.login1.Manager.Reboot",
                    "boolean:true",
                ]
                try:
                    subprocess.run(cmd)
                except Exception as e:
                    print(f"Reboot invocation failed: {e}", file=sys.stderr)
        dialog.connect("response", _on_reboot_response)
        dialog.present()

    def on_vte_done(self, vte, status):
        self.get_ui("ui_box_vte_buttons").set_visible(True)

        try:
            exit_code = os.waitstatus_to_exitcode(status)
        except ValueError:
            exit_code = status
        success = exit_code == 0
        reboot_pending = check_is_reboot_pending()
        self.get_ui("ui_button_reboot").set_sensitive(success and reboot_pending)

        for w in self.op_widgets:
            w.set_sensitive(True)
        if success:
            self.ui_apply_chg_button.set_sensitive(False)
        else:
            self.ui_apply_chg_button.set_sensitive(self.check_initials())

        status_label = self.get_ui("ui_vte_status_label")
        if status_label is not None:
            if success:
                markup = f'<span foreground="mediumspringgreen">{_("Operation completed successfully.")}</span>'
            else:
                markup = f'<span foreground="tomato">{_("Operation failed (exit code {code}). Please review the log above.").format(code=exit_code)}</span>'
            status_label.set_markup(markup)

        if self.apt_opr in ("install-nvidia", "install-nouveau", "update", "prime-mode", "install-ai-tools"):
            nvidia.reopen_cache()
            self.refresh_prime_ui()
            self.refresh_ai_ui()

        if self.apt_opr == "update":
            actual = nvidia.source()
            self.ui_repo_switch.handler_block(self.mirror_handler_id)
            try:
                self.ui_repo_switch.set_state(actual)
            finally:
                self.ui_repo_switch.handler_unblock(self.mirror_handler_id)
            self.state = actual

        if (
            success
            and self.apt_opr in ("install-nvidia", "install-nouveau", "update")
            and not self.disabled_no_devices
        ):
            self.create_gpu_drivers()

    def update_vte_color(self, vte):
        try:
            bg = Gdk.RGBA()
            bg.parse("#0f141c")
            fg = Gdk.RGBA()
            fg.parse("#e2e8f0")
            vte.set_color_background(bg)
            vte.set_color_foreground(fg)
        except Exception as e:
            print(f"Warning: Failed to set VTE colors: {e}", file=sys.stderr)

    def vte_start(self, params):
        for w in self.op_widgets:
            w.set_sensitive(False)
        self.get_ui("ui_box_vte_buttons").hide()
        self.get_ui("ui_vte_status_label").set_text("")
        self.ui_main_stack.set_visible_child_name("page_vte")
        self.vte.spawn_async(
            Vte.PtyFlags.DEFAULT,
            os.environ.get("HOME", "/tmp"),
            params,
            None,
            GLib.SpawnFlags.DEFAULT,
            None,
            None,
            -1,
            None,
            None,
        )

    def check_secondary_gpu(self):
        self.initial_sec_gpu_state = package.check_sec_state()
        if self.initial_sec_gpu_state:
            self.ui_info_stack.set_visible_child(self.ui_enabled_gpu_box)
        else:
            self.ui_info_stack.set_visible_child(self.ui_disabled_gpu_box)

        if getattr(self, "disabled_no_devices", False):
            if self.ui_disable_check_button.get_parent() is not None:
                self.ui_controller_box.remove(self.ui_disable_check_button)
            return

        if not any(dev.is_secondary_gpu for dev in self.nvidia_devices):
            if self.ui_disable_check_button.get_parent() is not None:
                self.ui_controller_box.remove(self.ui_disable_check_button)

    def create_gpu_drivers(self):
        if len(self.nvidia_devices) == 0 and not self.is_debug:
            self.ui_main_stack.set_visible_child(self.ui_novidia_box)
            return

        self.ui_main_stack.set_visible_child_name("page_main")

        for toggle in self.drv_arr:
            self.ui_gpu_box.remove(toggle)
        for gpu_info in self.gpu_info_arr:
            self.ui_gpu_info_box.remove(gpu_info)
        self.drv_arr = []
        self.gpu_info_arr = []
        self.driver_buttons = []

        for nvidia_device in self.nvidia_devices:
            gpu_info = self.gpu_box(nvidia_device)
            self.gpu_info_arr.append(gpu_info)
            self.ui_gpu_info_box.pack_start(gpu_info, True, True, 5)

        # Build auto-detection engine card above driver selection
        if hasattr(self, "auto_detect_card") and self.auto_detect_card.get_parent() is not None:
            self.auto_detect_card.get_parent().remove(self.auto_detect_card)
        self.auto_detect_card = self.build_auto_detect_card()
        self.ui_controller_box.pack_start(self.auto_detect_card, False, False, 4)
        self.ui_controller_box.reorder_child(self.auto_detect_card, 1)

        self.nvidia_drivers = nvidia.drivers(gpus=self.nvidia_devices)
        self.filtered_nvidia_drivers = []
        for index, nvidia_driver in enumerate(self.nvidia_drivers):
            if index == 0:
                self.filtered_nvidia_drivers.append(nvidia_driver)
            else:
                if self.state:
                    if nvidia_driver.repo == "NVIDIA" or nvidia_driver.installed:
                        self.filtered_nvidia_drivers.append(nvidia_driver)
                else:
                    self.filtered_nvidia_drivers.append(nvidia_driver)

        self.nvidia_drivers = self.filtered_nvidia_drivers

        for index, nvidia_driver in enumerate(self.nvidia_drivers):
            toggle = self.driver_box(
                nvidia_driver.package,
                nvidia_driver.version,
                nvidia_driver.type,
                nvidia_driver.repo,
                is_recommended=getattr(nvidia_driver, "is_recommended", False),
                rec_reason=getattr(nvidia_driver, "recommendation_reason", ""),
            )

            if nvidia_driver.installed:
                self.initial_gpu_driver = nvidia_driver
                self.toggled_driver = nvidia_driver
            toggle.set_active(nvidia_driver.installed)
            toggle.connect("toggled", self.on_drv_toggled, nvidia_driver)
            self.drv_arr.append(toggle)
            self.ui_gpu_box.pack_start(toggle, True, True, 5)

        self.ui_gpu_info_box.show_all()
        self.ui_gpu_box.show_all()
        self.ui_apply_chg_button.set_sensitive(self.check_initials())

    def build_auto_detect_card(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.get_style_context().add_class("auto-detect-card")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_icon = Gtk.Label(label="✨")
        lbl_title = Gtk.Label()
        lbl_title.set_markup('<span font_weight="bold" foreground="#10B981">Kart Otomatik Algılama &amp; Sürücü Tavsiye Motoru</span>')
        header.pack_start(lbl_icon, False, False, 0)
        header.pack_start(lbl_title, False, False, 0)
        card.pack_start(header, False, False, 0)

        dev = self.nvidia_devices[0] if self.nvidia_devices else None
        dev_name = dev.device_name if dev else _("NVIDIA Grafik Kartı")
        arch_name = getattr(dev, "architecture", "Modern") if dev else "Modern"
        rec_driver = getattr(dev, "recommended_driver", "nvidia-driver") if dev else "nvidia-driver"
        rec_reason = getattr(dev, "recommendation_reason", "") if dev else ""

        self.lbl_autodetect_info = Gtk.Label(xalign=0)
        info_text = f"<b>Donanım:</b> {dev_name}  •  <b>Mimari:</b> {arch_name}\n"
        info_text += f"<b>Önerilen Sürücü:</b> <span foreground='#38BDF8'><b>{rec_driver}</b></span>"
        if rec_reason:
            info_text += f" <span foreground='#94A3B8'>({rec_reason})</span>"
        self.lbl_autodetect_info.set_markup(info_text)
        self.lbl_autodetect_info.set_line_wrap(True)
        card.pack_start(self.lbl_autodetect_info, False, False, 0)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        btn_auto_select = Gtk.Button.new_with_label(_("✨ Önerilen Sürücüyü Otomatik Seç"))
        btn_auto_select.get_style_context().add_class("auto-detect-btn")
        btn_auto_select.connect("clicked", self.on_auto_select_recommended)
        btn_box.pack_start(btn_auto_select, False, False, 0)

        btn_diag = Gtk.Button.new_with_label(_("🔍 Donanım Raporu"))
        btn_diag.get_style_context().add_class("diag-btn")
        btn_diag.connect("clicked", self.on_show_hardware_diagnostics)
        btn_box.pack_start(btn_diag, False, False, 0)

        card.pack_start(btn_box, False, False, 2)

        self.lbl_autodetect_feedback = Gtk.Label(xalign=0)
        card.pack_start(self.lbl_autodetect_feedback, False, False, 0)

        card.show_all()
        return card

    def on_auto_select_recommended(self, button=None):
        rec_drv = None
        for drv in self.nvidia_drivers:
            if getattr(drv, "is_recommended", False):
                rec_drv = drv
                break
        if not rec_drv and len(self.nvidia_drivers) > 1:
            rec_drv = self.nvidia_drivers[1]
        elif not rec_drv and len(self.nvidia_drivers) > 0:
            rec_drv = self.nvidia_drivers[0]

        if rec_drv:
            for idx, drv in enumerate(self.nvidia_drivers):
                if drv == rec_drv:
                    if idx < len(self.drv_arr):
                        self.drv_arr[idx].set_active(True)
                        self.toggled_driver = drv
                    break

            if hasattr(self, "lbl_autodetect_feedback"):
                self.lbl_autodetect_feedback.set_markup(
                    f'<span foreground="#10B981" font_weight="bold">✓ Önerilen sürücü ({rec_drv.package} v{rec_drv.version}) başarıyla seçildi!</span>'
                )
            self.ui_apply_chg_button.set_sensitive(self.check_initials())

    def on_show_hardware_diagnostics(self, button=None):
        dialog = Gtk.Dialog(
            title=_("🔍 GPU & Donanım Tanılama Raporu"),
            transient_for=self.ui_main_window,
            use_header_bar=True,
        )
        dialog.set_default_size(580, 480)
        dialog.add_button(_("📋 Panoya Kopyala"), Gtk.ResponseType.APPLY)
        dialog.add_button(_("Kapat"), Gtk.ResponseType.CLOSE)

        content_area = dialog.get_content_area()
        content_area.set_spacing(10)
        content_area.set_margin_start(12)
        content_area.set_margin_end(12)
        content_area.set_margin_top(12)
        content_area.set_margin_bottom(12)

        lbl = Gtk.Label(xalign=0)
        lbl.set_markup('<span font_weight="bold" font_size="large" foreground="#38BDF8">📊 Sistem Grafik Donanım Raporu</span>')
        content_area.pack_start(lbl, False, False, 0)

        report_text = detector.generate_hardware_report()

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        textview = Gtk.TextView()
        textview.set_editable(False)
        textview.set_cursor_visible(False)
        textview.set_monospace(True)
        textview.set_wrap_mode(Gtk.WrapMode.NONE)
        textview.get_buffer().set_text(report_text)
        scrolled.set_child(textview)
        content_area.pack_start(scrolled, True, True, 0)

        def _on_diag_response(dlg, response):
            if response == Gtk.ResponseType.APPLY:
                display = Gdk.Display.get_default()
                if display:
                    clipboard = display.get_clipboard()
                    clipboard.set(report_text)
            dlg.destroy()

        dialog.connect("response", _on_diag_response)
        dialog.present()

    def on_rescan_hardware(self, button=None):
        self.nvidia_devices = nvidia.graphics()
        marker_present = not package.check_sec_state()
        self.disabled_no_devices = (
            not self.nvidia_devices and marker_present and not self.is_debug
        )
        if self.ui_detected_gpu_label:
            detected = get_system_gpu_description()
            self.ui_detected_gpu_label.set_markup(
                f'<span foreground="#94A3B8"><b>Sistemdeki Donanım:</b> {detected}</span>'
            )
        if not self.disabled_no_devices and len(self.nvidia_devices) > 0:
            self.ui_main_stack.set_visible_child_name("page_main")
            self.create_gpu_drivers()
            self.ui_apply_chg_button.set_sensitive(True)
            self.ui_repo_switch.set_sensitive(True)
            self.refresh_telemetry_ui()
            self.refresh_prime_ui()
            self.refresh_ai_ui()
        else:
            self.ui_main_stack.set_visible_child(self.ui_novidia_box)

    def on_simulate_custom_gpu(self, gpu_type="ampere"):
        self.is_debug = True
        os.environ["PARSLINUX_NVI_DEBUG"] = "1"
        if gpu_type == "ada":
            arch, arch_desc, rec_pkg, rec_reason = detector.identify_architecture(0x2782, "NVIDIA GeForce RTX 4070 Ti")
            self.nvidia_devices = [
                nvidia.NvidiaDevice(
                    vendor_id=0x10DE,
                    vendor_name="NVIDIA Corporation",
                    device_id=0x2782,
                    device_name="NVIDIA GeForce RTX 4070 Ti [AD104] (Simüle)",
                    driver_name="nvidia",
                    driver_version="550.120",
                    is_secondary_gpu=False,
                    pci_slot="0000:01:00.0",
                    architecture=arch,
                    architecture_desc=arch_desc,
                    recommended_driver=rec_pkg,
                    recommendation_reason=rec_reason,
                )
            ]
        elif gpu_type == "kepler":
            arch, arch_desc, rec_pkg, rec_reason = detector.identify_architecture(0x1187, "NVIDIA GeForce GTX 760")
            self.nvidia_devices = [
                nvidia.NvidiaDevice(
                    vendor_id=0x10DE,
                    vendor_name="NVIDIA Corporation",
                    device_id=0x1187,
                    device_name="NVIDIA GeForce GTX 760 [GK104] (Simüle / Legacy)",
                    driver_name="nouveau",
                    driver_version=None,
                    is_secondary_gpu=False,
                    pci_slot="0000:01:00.0",
                    architecture=arch,
                    architecture_desc=arch_desc,
                    recommended_driver=rec_pkg,
                    recommendation_reason=rec_reason,
                )
            ]
        else: # ampere
            arch, arch_desc, rec_pkg, rec_reason = detector.identify_architecture(0x2503, "NVIDIA GeForce RTX 3060")
            self.nvidia_devices = [
                nvidia.NvidiaDevice(
                    vendor_id=0x10DE,
                    vendor_name="NVIDIA Corporation",
                    device_id=0x2503,
                    device_name="NVIDIA GeForce RTX 3060 [GA106] (Simüle)",
                    driver_name="nvidia",
                    driver_version="550.120",
                    is_secondary_gpu=False,
                    pci_slot="0000:01:00.0",
                    architecture=arch,
                    architecture_desc=arch_desc,
                    recommended_driver=rec_pkg,
                    recommendation_reason=rec_reason,
                )
            ]
        self.ui_main_stack.set_visible_child_name("page_main")
        self.create_gpu_drivers()
        self.ui_apply_chg_button.set_sensitive(True)
        self.ui_repo_switch.set_sensitive(True)
        self.refresh_telemetry_ui()
        self.refresh_prime_ui()
        self.refresh_ai_ui()

    def get_ui(self, object_name: str):
        return self.gtk_builder.get_object(object_name)

    def driver_box(self, drv_name, drv_ver, drv_type, drv_repo, is_recommended=False, rec_reason=""):
        toggle_ui = os.path.normpath(os.path.join(os.path.dirname(__file__), "../ui/driver_toggle.glade"))
        b = self._build_ui_file(toggle_ui)
        btn = b.get_object("ui_radio_button")
        btn.set_name(drv_name)

        name = b.get_object("ui_name_label")
        markup = self.lbl_markup(_("Driver"), drv_name)
        if is_recommended:
            markup += '  <span background="#059669" foreground="#ffffff" weight="bold" font_size="small">  ★ ÖNERİLEN  </span>'
        name.set_markup(markup)

        ver = b.get_object("ui_version_label")
        markup = self.lbl_markup(_("Version"), drv_ver)
        ver.set_markup(markup)

        desc_label = drv_type
        if is_recommended and rec_reason:
            desc_label = f"{drv_type} — {rec_reason}"
        markup = self.lbl_markup(_("Description"), desc_label, color="#10B981" if is_recommended else "dodgerblue")
        if drv_name == nouveau:
            markup = self.lbl_markup(
                _("Description"), drv_type, color="mediumspringgreen"
            )
        lbl = b.get_object("ui_driver_label")
        lbl.set_markup(markup)

        repo = b.get_object("ui_repo_label")
        markup = self.lbl_markup("Repo", drv_repo)
        repo.set_markup(markup)

        grp = None
        if len(self.driver_buttons) > 0:
            grp = self.driver_buttons[0]
        if hasattr(btn, "set_group"):
            btn.set_group(grp)
        elif hasattr(btn, "join_group"):
            btn.join_group(grp)
        btn.get_style_context().add_class("driver-card")
        self.driver_buttons.append(btn)
        return btn

    def gpu_box(self, device):
        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 4)
        name_str = device.device_name if hasattr(device, "device_name") else str(device)
        name_label = Gtk.Label(xalign=0)
        name_label.set_markup(f"<span font_weight='bold' font_size='12000' foreground='#f8fafc'>{name_str}</span>")
        box.pack_start(name_label, False, False, 0)

        details = []
        arch = getattr(device, "architecture", None)
        if arch:
            details.append(f"<b>Mimari:</b> {arch}")
        pci = getattr(device, "pci_slot", None)
        if pci:
            details.append(f"<b>PCI:</b> {pci}")
        mod = getattr(device, "driver_name", None)
        if mod:
            details.append(f"<b>Aktif Modül:</b> {mod}")

        if details:
            sub_label = Gtk.Label(xalign=0)
            sub_label.set_markup(f"<span font_size='small' foreground='#94a3b8'>{'   •   '.join(details)}</span>")
            box.pack_start(sub_label, False, False, 0)

        return box

    def lbl_markup(self, label, desc, color=None):
        if color:
            return f'<span> <b>{label}: </b> <span foreground="{color}">{desc}</span> </span>'
        else:
            return f"<span> <b>{label}: </b> <span>{desc}</span> </span>"

    def on_drv_toggled(self, radio_button, driver):
        if radio_button.get_active():
            self.toggled_driver = driver
        self.ui_apply_chg_button.set_sensitive(self.check_initials())

    def on_enable_button_clicked(self, button):
        pkg_bin = get_package_exec_path()
        params = ["/usr/bin/pkexec", pkg_bin, "enable-sec-gpu"]
        self.vte_start(params)

    def on_apply_button_clicked(self, button):
        pkg_bin = get_package_exec_path()
        params = ["/usr/bin/pkexec", pkg_bin]
        self.apt_opr = None
        disable_request = (
            self.initial_sec_gpu_state and self.ui_disable_check_button.get_active()
        )
        if disable_request:
            self.apt_opr = "disable-sec-gpu"
            params.append(self.apt_opr)
            self.vte_start(params)
        else:
            if self.toggled_driver and self.toggled_driver.package == nouveau:
                self.apt_opr = "install-nouveau"
                params.append(self.apt_opr)
            elif self.toggled_driver:
                self.apt_opr = "install-nvidia"
                driver_arg = self.toggled_driver.package
                version = self.toggled_driver.version
                if version:
                    nvidia.reopen_cache()
                    if not nvidia.has_pkg_version(
                        self.toggled_driver.package, version
                    ):
                        self._notify_version_gone()
                        self.create_gpu_drivers()
                        return
                    driver_arg = f"{self.toggled_driver.package}={version}"
                params += [
                    self.apt_opr,
                    f"linux-headers-{platform.uname().release}",
                    "linux-headers-amd64",
                    driver_arg,
                ]
            self.vte_start(params)

    def _notify_version_gone(self):
        dialog = Gtk.MessageDialog(
            transient_for=self.ui_main_window,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text=_("Selected version is no longer available"),
        )
        dialog.format_secondary_text(
            _("The package list has been refreshed. Please choose a driver again.")
        )
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.present()

    def on_about_button_clicked(self, button):
        if self.ui_about_dialog:
            self.ui_about_dialog.present()

    def check_initials(self):
        sec_gpu_changes = (
            self.initial_sec_gpu_state and self.ui_disable_check_button.get_active()
        )
        if self.toggled_driver is None:
            driver_changes = False
        else:
            driver_changes = self.toggled_driver != self.initial_gpu_driver
        return sec_gpu_changes or driver_changes

    def on_disable_checkbox_checked(self, button):
        self.ui_apply_chg_button.set_sensitive(self.check_initials())

    def on_nvidia_mirror_changed(self, button, state):
        pkg_bin = get_package_exec_path()
        params = ["/usr/bin/pkexec", pkg_bin, "update"]
        self.apt_opr = "update"
        self.vte_start(params)

    def setup_feature_tabs(self):
        self.feature_stack = Gtk.Stack()
        self.feature_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.feature_stack.set_transition_duration(200)

        self.feature_switcher = Gtk.StackSwitcher()
        self.feature_switcher.set_stack(self.feature_stack)
        self.feature_switcher.set_halign(Gtk.Align.CENTER)
        self.feature_switcher.set_margin_bottom(12)

        # Reparent ui_controller_box into feature_stack
        if self.ui_controller_box.get_parent() is not None:
            self.ui_controller_box.get_parent().remove(self.ui_controller_box)

        self.feature_stack.add_titled(self.ui_controller_box, "drivers", _("🎮 Sürücüler"))

        self.page_monitor = self.build_monitor_page()
        self.feature_stack.add_titled(self.page_monitor, "monitor", _("📊 Donanım & Güç"))

        self.page_gaming = self.build_gaming_page()
        self.feature_stack.add_titled(self.page_gaming, "gaming", _("🕹️ Oyun"))

        self.page_ai = self.build_ai_page()
        self.feature_stack.add_titled(self.page_ai, "ai_tools", _("🧠 Yapay Zeka (CUDA)"))

        self.ui_enabled_gpu_box.pack_start(self.feature_switcher, False, False, 0)
        self.ui_enabled_gpu_box.pack_start(self.feature_stack, True, True, 0)

    def build_monitor_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(6)
        box.set_margin_bottom(10)

        # 1. Telemetry Card
        card_mon = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card_mon.get_style_context().add_class("monitor-card")

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        lbl_title = Gtk.Label()
        lbl_title.set_markup('<span font_weight="bold" foreground="#38BDF8">📊 Canlı Donanım İzleme &amp; Sensörler</span>')
        lbl_title.set_halign(Gtk.Align.START)
        header_box.pack_start(lbl_title, True, True, 0)

        btn_refresh = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        btn_refresh.set_tooltip_text(_("Sensörleri Yenile"))
        btn_refresh.connect("clicked", lambda b: self.refresh_telemetry_ui())
        header_box.pack_end(btn_refresh, False, False, 0)
        card_mon.pack_start(header_box, False, False, 0)

        # GPU Model & Driver Label
        self.lbl_mon_gpu_title = Gtk.Label()
        self.lbl_mon_gpu_title.set_markup('<span font_weight="bold" font_size="small" foreground="#E2E8F0">NVIDIA Grafik Kartı</span>')
        self.lbl_mon_gpu_title.set_halign(Gtk.Align.START)
        card_mon.pack_start(self.lbl_mon_gpu_title, False, False, 0)

        # Grid of stats (2x2)
        grid = Gtk.Grid()
        grid.set_column_spacing(10)
        grid.set_row_spacing(10)
        grid.set_column_homogeneous(True)

        # Stat 1: Temp
        chip1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        chip1.get_style_context().add_class("stat-item")
        l1 = Gtk.Label(label="🌡️ GPU Sıcaklığı")
        l1.get_style_context().add_class("stat-label")
        l1.set_halign(Gtk.Align.START)
        self.lbl_temp = Gtk.Label()
        self.lbl_temp.get_style_context().add_class("stat-value")
        self.lbl_temp.set_halign(Gtk.Align.START)
        chip1.pack_start(l1, False, False, 0)
        chip1.pack_start(self.lbl_temp, False, False, 0)
        grid.attach(chip1, 0, 0, 1, 1)

        # Stat 2: Fan
        chip2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        chip2.get_style_context().add_class("stat-item")
        l2 = Gtk.Label(label="💨 Fan Hızı")
        l2.get_style_context().add_class("stat-label")
        l2.set_halign(Gtk.Align.START)
        self.lbl_fan = Gtk.Label()
        self.lbl_fan.get_style_context().add_class("stat-value")
        self.lbl_fan.set_halign(Gtk.Align.START)
        chip2.pack_start(l2, False, False, 0)
        chip2.pack_start(self.lbl_fan, False, False, 0)
        grid.attach(chip2, 1, 0, 1, 1)

        # Stat 3: Power & Load
        chip3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        chip3.get_style_context().add_class("stat-item")
        l3 = Gtk.Label(label="⚡ Güç & Kullanım")
        l3.get_style_context().add_class("stat-label")
        l3.set_halign(Gtk.Align.START)
        self.lbl_power = Gtk.Label()
        self.lbl_power.get_style_context().add_class("stat-value")
        self.lbl_power.set_halign(Gtk.Align.START)
        chip3.pack_start(l3, False, False, 0)
        chip3.pack_start(self.lbl_power, False, False, 0)
        grid.attach(chip3, 0, 1, 1, 1)

        # Stat 4: Driver Version
        chip4 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        chip4.get_style_context().add_class("stat-item")
        l4 = Gtk.Label(label="🧩 Sürücü Sürümü")
        l4.get_style_context().add_class("stat-label")
        l4.set_halign(Gtk.Align.START)
        self.lbl_driver_ver = Gtk.Label()
        self.lbl_driver_ver.get_style_context().add_class("stat-value")
        self.lbl_driver_ver.set_halign(Gtk.Align.START)
        chip4.pack_start(l4, False, False, 0)
        chip4.pack_start(self.lbl_driver_ver, False, False, 0)
        grid.attach(chip4, 1, 1, 1, 1)

        card_mon.pack_start(grid, False, False, 0)

        # VRAM Section
        vram_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.lbl_vram = Gtk.Label()
        self.lbl_vram.set_halign(Gtk.Align.START)
        self.bar_vram = Gtk.ProgressBar()
        vram_box.pack_start(self.lbl_vram, False, False, 0)
        vram_box.pack_start(self.bar_vram, False, False, 0)
        card_mon.pack_start(vram_box, False, False, 4)

        box.pack_start(card_mon, False, False, 0)

        # 2. PRIME Profile Card
        card_prime = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card_prime.get_style_context().add_class("prime-card")

        prime_header = Gtk.Label()
        prime_header.set_markup('<span font_weight="bold" foreground="#38BDF8">⚡ PRIME GPU Güç Profili (Melez Grafikler)</span>')
        prime_header.set_halign(Gtk.Align.START)
        card_prime.pack_start(prime_header, False, False, 0)

        prime_desc = Gtk.Label()
        prime_desc.set_markup('<span font_size="small" foreground="#94A3B8">Çift ekran kartlı dizüstü bilgisayarlarda batarya süresi ile grafik performansını belirleyin:</span>')
        prime_desc.set_line_wrap(True)
        prime_desc.set_halign(Gtk.Align.START)
        card_prime.pack_start(prime_desc, False, False, 0)

        self.lbl_active_prime = Gtk.Label()
        self.lbl_active_prime.set_halign(Gtk.Align.START)
        card_prime.pack_start(self.lbl_active_prime, False, False, 0)

        btn_prime_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_prime_box.set_homogeneous(True)

        self.btn_prime_intel = Gtk.Button(label=_("🍃 Tasarruf\n(Entegre)"))
        self.btn_prime_intel.get_style_context().add_class("prime-btn")
        self.btn_prime_intel.connect("clicked", lambda b: self.on_switch_prime("integrated"))

        self.btn_prime_demand = Gtk.Button(label=_("⚡ Hibrit\n(İsteğe Bağlı)"))
        self.btn_prime_demand.get_style_context().add_class("prime-btn")
        self.btn_prime_demand.connect("clicked", lambda b: self.on_switch_prime("on-demand"))

        self.btn_prime_nvidia = Gtk.Button(label=_("🚀 Performans\n(NVIDIA)"))
        self.btn_prime_nvidia.get_style_context().add_class("prime-btn")
        self.btn_prime_nvidia.connect("clicked", lambda b: self.on_switch_prime("nvidia"))

        btn_prime_box.pack_start(self.btn_prime_intel, True, True, 0)
        btn_prime_box.pack_start(self.btn_prime_demand, True, True, 0)
        btn_prime_box.pack_start(self.btn_prime_nvidia, True, True, 0)
        card_prime.pack_start(btn_prime_box, False, False, 4)

        box.pack_start(card_prime, False, False, 0)

        # 3. Hardware Fan & Power Limit Card
        card_ctrl = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card_ctrl.get_style_context().add_class("monitor-card")

        ctrl_header = Gtk.Label()
        ctrl_header.set_markup('<span font_weight="bold" foreground="#38BDF8">⚙️ Özel Fan Hızı &amp; Güç Sınırı (Power Limit)</span>')
        ctrl_header.set_halign(Gtk.Align.START)
        card_ctrl.pack_start(ctrl_header, False, False, 0)

        # Fan Scale Row
        row_fan = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl_fan_ctrl = Gtk.Label(label=_("💨 Fan Hızı (%):"))
        lbl_fan_ctrl.set_halign(Gtk.Align.START)
        fan_info = monitor.get_fan_control_info()
        self.scale_fan = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 20, 100, 5)
        self.scale_fan.set_value(fan_info["custom_speed"] or 50)
        self.scale_fan.set_digits(0)
        self.scale_fan.set_value_pos(Gtk.PositionType.RIGHT)
        btn_apply_fan = Gtk.Button(label=_("Uygula"))
        btn_apply_fan.get_style_context().add_class("prime-btn")
        btn_apply_fan.connect("clicked", lambda b: self.on_apply_fan_speed())
        row_fan.pack_start(lbl_fan_ctrl, False, False, 0)
        row_fan.pack_start(self.scale_fan, True, True, 0)
        row_fan.pack_end(btn_apply_fan, False, False, 0)
        card_ctrl.pack_start(row_fan, False, False, 2)

        # Power Scale Row
        row_power = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl_power_ctrl = Gtk.Label(label=_("⚡ Güç Sınırı (W):"))
        lbl_power_ctrl.set_halign(Gtk.Align.START)
        power_info = monitor.get_power_limit_info()
        self.scale_power = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, power_info["min_watts"], power_info["max_watts"], 10)
        self.scale_power.set_value(power_info["target_watts"])
        self.scale_power.set_digits(0)
        self.scale_power.set_value_pos(Gtk.PositionType.RIGHT)
        btn_apply_power = Gtk.Button(label=_("Uygula"))
        btn_apply_power.get_style_context().add_class("prime-btn")
        btn_apply_power.connect("clicked", lambda b: self.on_apply_power_limit())
        row_power.pack_start(lbl_power_ctrl, False, False, 0)
        row_power.pack_start(self.scale_power, True, True, 0)
        row_power.pack_end(btn_apply_power, False, False, 0)
        card_ctrl.pack_start(row_power, False, False, 2)

        box.pack_start(card_ctrl, False, False, 0)

        # 4. Overclocking Card
        card_oc = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card_oc.get_style_context().add_class("monitor-card")

        oc_header = Gtk.Label()
        oc_header.set_markup('<span font_weight="bold" foreground="#38BDF8">🚀 GPU Hız Aşırtma &amp; Frekans Ofseti (Overclocking)</span>')
        oc_header.set_halign(Gtk.Align.START)
        card_oc.pack_start(oc_header, False, False, 0)

        oc_desc = Gtk.Label()
        oc_desc.set_markup('<span font_size="small" foreground="#94A3B8">NVIDIA GPU çekirdek ve video belleği için saat frekansı ofsetlerini ayarlayın:</span>')
        oc_desc.set_line_wrap(True)
        oc_desc.set_halign(Gtk.Align.START)
        card_oc.pack_start(oc_desc, False, False, 0)

        oc_info = monitor.get_overclock_settings()

        # Core Clock Offset Row
        row_core = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl_core = Gtk.Label(label=_("🎯 Çekirdek (Core MHz):"))
        lbl_core.set_halign(Gtk.Align.START)
        self.scale_core_oc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -200, 300, 10)
        self.scale_core_oc.set_value(oc_info["core_offset"])
        self.scale_core_oc.set_digits(0)
        self.scale_core_oc.set_value_pos(Gtk.PositionType.RIGHT)
        row_core.pack_start(lbl_core, False, False, 0)
        row_core.pack_start(self.scale_core_oc, True, True, 0)
        card_oc.pack_start(row_core, False, False, 2)

        # Memory Clock Offset Row
        row_mem = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl_mem = Gtk.Label(label=_("🧠 Bellek (Memory MHz):"))
        lbl_mem.set_halign(Gtk.Align.START)
        self.scale_mem_oc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -500, 1500, 25)
        self.scale_mem_oc.set_value(oc_info["mem_offset"])
        self.scale_mem_oc.set_digits(0)
        self.scale_mem_oc.set_value_pos(Gtk.PositionType.RIGHT)
        row_mem.pack_start(lbl_mem, False, False, 0)
        row_mem.pack_start(self.scale_mem_oc, True, True, 0)
        card_oc.pack_start(row_mem, False, False, 2)

        # Buttons Row
        btn_oc_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_oc_box.set_halign(Gtk.Align.END)

        btn_reset_oc = Gtk.Button(label=_("🔄 Varsayılana Sıfırla (0 MHz)"))
        btn_reset_oc.connect("clicked", lambda b: self.on_reset_overclock())

        btn_apply_oc = Gtk.Button(label=_("⚡ Hız Aşırtmayı Uygula"))
        btn_apply_oc.get_style_context().add_class("suggested-action")
        btn_apply_oc.connect("clicked", lambda b: self.on_apply_overclock())

        btn_oc_box.pack_start(btn_reset_oc, False, False, 0)
        btn_oc_box.pack_start(btn_apply_oc, False, False, 0)
        card_oc.pack_start(btn_oc_box, False, False, 4)

        box.pack_start(card_oc, False, False, 0)

        self.refresh_telemetry_ui()
        self.refresh_prime_ui()
        return box

    def build_gaming_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(6)
        box.set_margin_bottom(10)

        card_game = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        card_game.get_style_context().add_class("card-box")

        header = Gtk.Label()
        header.set_markup('<span font_weight="bold" foreground="#38BDF8">🕹️ Oyun Hızlandırıcı &amp; PRIME Offload</span>')
        header.set_halign(Gtk.Align.START)
        card_game.pack_start(header, False, False, 0)

        desc = Gtk.Label()
        desc.set_markup('<span font_size="small" foreground="#94A3B8">Oyunları otomatik olarak yüksek performanslı NVIDIA GPU ve Vulkan DXVK katmanlarıyla çalıştırın.</span>')
        desc.set_line_wrap(True)
        desc.set_halign(Gtk.Align.START)
        card_game.pack_start(desc, False, False, 0)

        # Global Offload Switch
        row_switch = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lbl_switch = Gtk.Label()
        lbl_switch.set_markup('<b>Tüm Oyunlar İçin Otomatik NVIDIA Offload</b>')
        lbl_switch.set_halign(Gtk.Align.START)
        self.switch_game_offload = Gtk.Switch()
        self.switch_game_offload.set_active(monitor.get_game_offload_status())
        self.switch_game_offload.connect("state-set", self.on_toggle_game_offload)
        row_switch.pack_start(lbl_switch, True, True, 0)
        row_switch.pack_end(self.switch_game_offload, False, False, 0)
        card_game.pack_start(row_switch, False, False, 4)

        # Launchers Box
        lbl_launchers = Gtk.Label()
        lbl_launchers.set_markup('<span font_weight="bold" font_size="small" foreground="#E2E8F0">Algılanan Oyun Başlatıcıları:</span>')
        lbl_launchers.set_halign(Gtk.Align.START)
        card_game.pack_start(lbl_launchers, False, False, 4)

        self.box_launchers = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        launchers = monitor.get_detected_game_launchers()
        for l in launchers:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            status_color = "#4ADE80" if l["installed"] else "#64748B"
            status_text = "✓ Algılandı" if l["installed"] else "✗ Yüklü Değil"
            lbl = Gtk.Label()
            lbl.set_markup(f'🎮 <b>{l["name"]}</b>: <span foreground="{status_color}">{status_text}</span>')
            lbl.set_halign(Gtk.Align.START)
            row.pack_start(lbl, True, True, 0)
            if l["installed"]:
                btn_run = Gtk.Button(label=_("NVIDIA ile Başlat"))
                btn_run.get_style_context().add_class("prime-btn")
                bin_name = l["bin"]
                btn_run.connect("clicked", lambda b, cmd=bin_name: self.launch_game_with_nvidia(cmd))
                row.pack_end(btn_run, False, False, 0)
            self.box_launchers.pack_start(row, False, False, 0)

        card_game.pack_start(self.box_launchers, False, False, 4)

        # Quick Test Button
        btn_test = Gtk.Button(label=_("🚀 3D Grafik Testi Başlat (vkcube / glxgears)"))
        btn_test.get_style_context().add_class("sim-button")
        btn_test.set_halign(Gtk.Align.CENTER)
        btn_test.connect("clicked", self.on_run_graphics_test)
        card_game.pack_start(btn_test, False, False, 8)

        box.pack_start(card_game, False, False, 0)

        # MangoHud Card
        card_hud = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card_hud.get_style_context().add_class("card-box")

        hud_header = Gtk.Label()
        hud_header.set_markup('<span font_weight="bold" foreground="#38BDF8">🎯 Oyun İçi Canlı HUD &amp; FPS Göstergesi (MangoHud)</span>')
        hud_header.set_halign(Gtk.Align.START)
        card_hud.pack_start(hud_header, False, False, 0)

        hud_desc = Gtk.Label()
        hud_desc.set_markup('<span font_size="small" foreground="#94A3B8">Oyun oynarken ekranın sol üstünde anlık FPS, GPU/CPU sıcaklığı ve VRAM kullanımını gösterir. (Kısayol: Sağ Shift + F12)</span>')
        hud_desc.set_line_wrap(True)
        hud_desc.set_halign(Gtk.Align.START)
        card_hud.pack_start(hud_desc, False, False, 0)

        hud_status = monitor.get_mangohud_status()
        row_hud = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lbl_hud_enable = Gtk.Label()
        lbl_hud_enable.set_markup('<b>ParsLinux Oyun İçi Telemetri Katmanını Etkinleştir</b>')
        lbl_hud_enable.set_halign(Gtk.Align.START)

        self.switch_mangohud = Gtk.Switch()
        self.switch_mangohud.set_active(hud_status["enabled"])
        self.switch_mangohud.connect("state-set", self.on_toggle_mangohud)
        row_hud.pack_start(lbl_hud_enable, True, True, 0)
        row_hud.pack_end(self.switch_mangohud, False, False, 0)
        card_hud.pack_start(row_hud, False, False, 4)

        if not hud_status["installed"]:
            row_install = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            lbl_not_inst = Gtk.Label()
            lbl_not_inst.set_markup('<span foreground="#F59E0B" font_size="small">⚠️ MangoHud sistemde kurulu değil.</span>')
            lbl_not_inst.set_halign(Gtk.Align.START)
            btn_inst_hud = Gtk.Button(label=_("📦 MangoHud Yükle"))
            btn_inst_hud.get_style_context().add_class("prime-btn")
            btn_inst_hud.connect("clicked", lambda b: self.on_install_mangohud())
            row_install.pack_start(lbl_not_inst, True, True, 0)
            row_install.pack_end(btn_inst_hud, False, False, 0)
            card_hud.pack_start(row_install, False, False, 2)

        box.pack_start(card_hud, False, False, 0)
        return box

    def build_ai_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(6)
        box.set_margin_bottom(10)

        card_ai = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        card_ai.get_style_context().add_class("ai-card")

        ai_header = Gtk.Label()
        ai_header.set_markup('<span font_weight="bold" foreground="#A78BFA">🧠 Yapay Zeka &amp; Geliştirici Kütüphaneleri</span>')
        ai_header.set_halign(Gtk.Align.START)
        card_ai.pack_start(ai_header, False, False, 0)

        ai_desc = Gtk.Label()
        ai_desc.set_markup('<span font_size="small" foreground="#94A3B8">Yapay zeka modelleri (PyTorch, TensorFlow, Stable Diffusion), 3D render (Blender) ve CUDA uygulamaları için gerekli geliştirici bileşenlerini tek tıkla kurun.</span>')
        ai_desc.set_line_wrap(True)
        ai_desc.set_halign(Gtk.Align.START)
        card_ai.pack_start(ai_desc, False, False, 0)

        # Items
        self.ai_chk_cuda = Gtk.CheckButton(label=_("🟢 NVIDIA CUDA Toolkit (nvcc, runtimes & headers)"))
        self.ai_chk_cuda.set_active(True)
        self.lbl_status_cuda = Gtk.Label()
        self.lbl_status_cuda.set_halign(Gtk.Align.START)

        self.ai_chk_cudnn = Gtk.CheckButton(label=_("🧬 NVIDIA cuDNN (Derin Sinir Ağları Kütüphanesi)"))
        self.ai_chk_cudnn.set_active(True)
        self.lbl_status_cudnn = Gtk.Label()
        self.lbl_status_cudnn.set_halign(Gtk.Align.START)

        self.ai_chk_trt = Gtk.CheckButton(label=_("🚀 NVIDIA TensorRT (Yüksek Hızlı Çıkarım Motoru)"))
        self.ai_chk_trt.set_active(True)
        self.lbl_status_trt = Gtk.Label()
        self.lbl_status_trt.set_halign(Gtk.Align.START)

        item_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for chk, lbl in [(self.ai_chk_cuda, self.lbl_status_cuda),
                         (self.ai_chk_cudnn, self.lbl_status_cudnn),
                         (self.ai_chk_trt, self.lbl_status_trt)]:
            r_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            r_box.pack_start(chk, False, False, 0)
            r_box.pack_start(lbl, False, False, 0)
            item_box.pack_start(r_box, False, False, 0)

        card_ai.pack_start(item_box, False, False, 0)

        btn_install_ai = Gtk.Button(label=_("🚀 Seçilen Geliştirici Bileşenlerini Kur"))
        btn_install_ai.get_style_context().add_class("ai-btn")
        btn_install_ai.set_halign(Gtk.Align.CENTER)
        btn_install_ai.connect("clicked", self.on_install_ai_clicked)
        card_ai.pack_start(btn_install_ai, False, False, 6)

        box.pack_start(card_ai, False, False, 0)
        self.refresh_ai_ui()
        return box

    def refresh_telemetry_ui(self):
        if not hasattr(self, "lbl_temp"):
            return True
        try:
            data = monitor.get_gpu_telemetry(simulated=self.is_debug)
            if not data or not data.get("available"):
                return True

            temp = data.get("temp", 45)
            color = "#4ADE80" if temp < 60 else ("#FBBF24" if temp < 80 else "#F87171")
            self.lbl_temp.set_markup(f'<span font_weight="bold" foreground="{color}">{temp} °C</span>')

            fan = data.get("fan", 0)
            self.lbl_fan.set_markup(f'<span font_weight="bold">{fan} %</span>')

            power = data.get("power", 0)
            util = data.get("utilization", 0)
            self.lbl_power.set_markup(f'<span font_weight="bold">{power} W • %{util}</span>')

            drv = data.get("driver", "Bilinmiyor")
            self.lbl_driver_ver.set_markup(f'<span font_weight="bold">v{drv}</span>')

            v_used = data.get("vram_used", 0)
            v_total = data.get("vram_total", 8192)
            u_gb = v_used / 1024.0
            t_gb = v_total / 1024.0
            fraction = min(1.0, max(0.0, v_used / float(v_total)))
            self.bar_vram.set_fraction(fraction)
            self.lbl_vram.set_markup(
                f'<span font_size="small">💾 VRAM: <b>{u_gb:.1f} GB</b> / {t_gb:.1f} GB (%{fraction*100:.0f})</span>'
            )

            name = data.get("name", "NVIDIA GPU")
            self.lbl_mon_gpu_title.set_markup(f'<span font_weight="bold" font_size="small" foreground="#E2E8F0">{name}</span>')
        except Exception as e:
            print(f"Warning: Failed to update telemetry: {e}", file=sys.stderr)
        return True

    def refresh_prime_ui(self):
        if not hasattr(self, "lbl_active_prime"):
            return
        mode = monitor.get_prime_profile()
        mode_titles = {
            "integrated": _("🍃 Tasarruf (Entegre GPU Aktif - NVIDIA Kapalı)"),
            "on-demand": _("⚡ Hibrit (İsteğe Bağlı / PRIME Render Offload)"),
            "nvidia": _("🚀 Performans (NVIDIA Kartı Sürekli Aktif)"),
        }
        title = mode_titles.get(mode, mode)
        self.lbl_active_prime.set_markup(
            f'<span font_size="small" foreground="#38BDF8"><b>Aktif Profil:</b> {title}</span>'
        )

        # Highlight buttons
        for btn in (self.btn_prime_intel, self.btn_prime_demand, self.btn_prime_nvidia):
            btn.get_style_context().remove_class("active")
        if mode == "integrated":
            self.btn_prime_intel.get_style_context().add_class("active")
        elif mode == "nvidia":
            self.btn_prime_nvidia.get_style_context().add_class("active")
        else:
            self.btn_prime_demand.get_style_context().add_class("active")

    def refresh_ai_ui(self):
        if not hasattr(self, "lbl_status_cuda"):
            return
        status = monitor.get_ai_stack_status()

        if status["cuda"]["installed"]:
            v = status["cuda"]["version"] or "Kurulu"
            self.lbl_status_cuda.set_markup(f'<span font_size="small" foreground="#4ADE80">   ✓ Kurulu: {v}</span>')
        else:
            self.lbl_status_cuda.set_markup('<span font_size="small" foreground="#94A3B8">   ✗ Kurulu Değil</span>')

        if status["cudnn"]["installed"]:
            v = status["cudnn"]["version"] or "Kurulu"
            self.lbl_status_cudnn.set_markup(f'<span font_size="small" foreground="#4ADE80">   ✓ Kurulu: {v}</span>')
        else:
            self.lbl_status_cudnn.set_markup('<span font_size="small" foreground="#94A3B8">   ✗ Kurulu Değil</span>')

        if status["tensorrt"]["installed"]:
            v = status["tensorrt"]["version"] or "Kurulu"
            self.lbl_status_trt.set_markup(f'<span font_size="small" foreground="#4ADE80">   ✓ Kurulu: {v}</span>')
        else:
            self.lbl_status_trt.set_markup('<span font_size="small" foreground="#94A3B8">   ✗ Kurulu Değil</span>')

    def on_switch_prime(self, mode):
        self.apt_opr = "prime-mode"
        exec_path = get_package_exec_path()
        params = ["/usr/bin/pkexec", exec_path, "prime-mode", mode]
        self.vte_start(params)

    def on_install_ai_clicked(self, button):
        pkgs = []
        if self.ai_chk_cuda.get_active():
            pkgs.append("nvidia-cuda-toolkit")
        if self.ai_chk_cudnn.get_active():
            pkgs.append("libcudnn8")
        if self.ai_chk_trt.get_active():
            pkgs.append("tensorrt")
        if not pkgs:
            return
        self.apt_opr = "install-ai-tools"
        exec_path = get_package_exec_path()
        params = ["/usr/bin/pkexec", exec_path, "install-ai-tools", *pkgs]
        self.vte_start(params)

    def on_apply_fan_speed(self):
        val = int(self.scale_fan.get_value())
        self.apt_opr = "set-fan-speed"
        exec_path = get_package_exec_path()
        params = ["/usr/bin/pkexec", exec_path, "set-fan-speed", str(val)]
        self.vte_start(params)

    def on_apply_power_limit(self):
        val = int(self.scale_power.get_value())
        self.apt_opr = "set-power-limit"
        exec_path = get_package_exec_path()
        params = ["/usr/bin/pkexec", exec_path, "set-power-limit", str(val)]
        self.vte_start(params)

    def on_toggle_game_offload(self, switch, state):
        exec_path = get_package_exec_path()
        arg = "on" if state else "off"
        params = ["/usr/bin/pkexec", exec_path, "set-game-offload", arg]
        self.vte_start(params)

    def on_apply_overclock(self):
        core = int(self.scale_core_oc.get_value())
        mem = int(self.scale_mem_oc.get_value())
        self.apt_opr = "set-overclock"
        exec_path = get_package_exec_path()
        params = ["/usr/bin/pkexec", exec_path, "set-overclock", str(core), str(mem)]
        self.vte_start(params)

    def on_reset_overclock(self):
        if hasattr(self, "scale_core_oc"):
            self.scale_core_oc.set_value(0)
        if hasattr(self, "scale_mem_oc"):
            self.scale_mem_oc.set_value(0)
        self.on_apply_overclock()

    def on_toggle_mangohud(self, switch, state):
        monitor.set_mangohud_profile(state)

    def on_install_mangohud(self):
        self.apt_opr = "install-extra"
        exec_path = get_package_exec_path()
        params = ["/usr/bin/pkexec", exec_path, "install-extra", "mangohud"]
        self.vte_start(params)

    def on_create_snapshot_clicked(self):
        if not monitor.is_timeshift_installed():
            dialog = Gtk.MessageDialog(
                transient_for=self.ui_main_window,
                modal=True,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK_CANCEL,
                text=_("Timeshift Kurulu Değil"),
            )
            dialog.format_secondary_text(
                _("Sistem geri yükleme noktası oluşturmak için Timeshift gereklidir. Şimdi Timeshift paketini yüklemek ister misiniz?")
            )
            def _on_install_timeshift(dlg, resp):
                dlg.destroy()
                if resp == Gtk.ResponseType.OK:
                    exec_path = get_package_exec_path()
                    self.apt_opr = "install-extra"
                    self.vte_start(["/usr/bin/pkexec", exec_path, "install-extra", "timeshift"])
            dialog.connect("response", _on_install_timeshift)
            dialog.present()
            return

        dialog = Gtk.MessageDialog(
            transient_for=self.ui_main_window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=_("Sistem Geri Yükleme Noktası Oluştur"),
        )
        dialog.format_secondary_text(
            _("Sürücü ve donanım yapılandırması öncesinde Timeshift ile sistem yedeği alınsın mı?")
        )
        def _on_confirm_snapshot(dlg, resp):
            dlg.destroy()
            if resp == Gtk.ResponseType.OK:
                exec_path = get_package_exec_path()
                self.apt_opr = "create-snapshot"
                self.vte_start(["/usr/bin/pkexec", exec_path, "create-snapshot", "ParsLinux-NVI-Backup"])
        dialog.connect("response", _on_confirm_snapshot)
        dialog.present()

    def launch_game_with_nvidia(self, bin_name):
        env = os.environ.copy()
        env["__NV_PRIME_RENDER_OFFLOAD"] = "1"
        env["__GLX_VENDOR_LIBRARY_NAME"] = "nvidia"
        env["__VK_LAYER_NV_optimus"] = "NVIDIA_only"
        if monitor.get_mangohud_status()["enabled"]:
            env["MANGOHUD"] = "1"
        try:
            subprocess.Popen([bin_name], env=env)
        except Exception as e:
            print(f"Failed to launch {bin_name}: {e}", file=sys.stderr)

    def on_run_graphics_test(self, button):
        env = os.environ.copy()
        env["__NV_PRIME_RENDER_OFFLOAD"] = "1"
        env["__GLX_VENDOR_LIBRARY_NAME"] = "nvidia"
        if monitor.get_mangohud_status()["enabled"]:
            env["MANGOHUD"] = "1"
        for cmd in ("vkcube", "glxgears"):
            if shutil.which(cmd):
                try:
                    subprocess.Popen([cmd], env=env)
                    return
                except Exception:
                    pass
        print("Neither vkcube nor glxgears installed for benchmark test", file=sys.stderr)

    def start_tray_indicator(self):
        tray_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tray.py")
        try:
            subprocess.Popen([sys.executable, tray_script])
        except Exception as e:
            print(f"Failed to start tray indicator: {e}", file=sys.stderr)

