#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ParsLinux Nvidia Installer - Hardware Monitor, PRIME Profiler & AI Stack Helper
Provides telemetry, power profiles, and AI developer toolkit status.
"""

import os
import shutil
import subprocess
import time
import math
import glob

# Primary and legacy GPU disable markers
PRIMARY_DISABLE_PATH = "/var/cache/parslinux-nvi-disable-gpu"
LEGACY_DISABLE_PATH = "/var/cache/pni-disable-gpu"
PRIME_STATE_FILE = "/var/cache/parslinux-nvi-prime-mode"


def is_gpu_disabled():
    return os.path.isfile(PRIMARY_DISABLE_PATH) or os.path.isfile(LEGACY_DISABLE_PATH)


def get_prime_profile():
    """
    Returns the active PRIME power profile:
    - 'integrated': Secondary NVIDIA GPU is completely powered down (saving battery).
    - 'on-demand': Hybrid mode with PRIME Render Offload (active when needed).
    - 'nvidia': High performance mode (always on NVIDIA GPU).
    """
    if is_gpu_disabled():
        return "integrated"

    if os.path.isfile(PRIME_STATE_FILE):
        try:
            with open(PRIME_STATE_FILE, "r") as f:
                mode = f.read().strip()
                if mode in ("integrated", "on-demand", "nvidia"):
                    return mode
        except OSError:
            pass

    # Check system prime-select if installed
    prime_select = shutil.which("prime-select")
    if prime_select:
        try:
            out = subprocess.check_output([prime_select, "get-current"], text=True, stderr=subprocess.DEVNULL).strip()
            if "intel" in out or "integrated" in out:
                return "integrated"
            elif "on-demand" in out:
                return "on-demand"
            elif "nvidia" in out:
                return "nvidia"
        except Exception:
            pass

    return "on-demand"


def get_gpu_telemetry(simulated=False):
    """
    Gathers GPU telemetry metrics (Temperature, Fan Speed, VRAM, Power, Utilization).
    Returns real metrics via nvidia-smi if available, or simulated metrics if in debug mode.
    """
    # 1. Try real nvidia-smi if not forced simulated
    if not simulated:
        smi = shutil.which("nvidia-smi")
        if smi:
            try:
                cmd = [
                    smi,
                    "--query-gpu=name,temperature.gpu,fan.speed,memory.used,memory.total,power.draw,utilization.gpu,driver_version",
                    "--format=csv,noheader,nounits",
                ]
                output = subprocess.check_output(cmd, text=True, timeout=2).strip()
                lines = output.splitlines()
                if lines:
                    parts = [p.strip() for p in lines[0].split(",")]
                    if len(parts) >= 8:
                        def safe_int(v, default=0):
                            try:
                                return int(float(v))
                            except (ValueError, TypeError):
                                return default

                        def safe_float(v, default=0.0):
                            try:
                                return float(v)
                            except (ValueError, TypeError):
                                return default

                        return {
                            "available": True,
                            "simulated": False,
                            "name": parts[0],
                            "temp": safe_int(parts[1], 45),
                            "fan": safe_int(parts[2], 0),
                            "vram_used": safe_int(parts[3], 0),
                            "vram_total": max(safe_int(parts[4], 8192), 1),
                            "power": safe_float(parts[5], 35.0),
                            "utilization": safe_int(parts[6], 10),
                            "driver": parts[7],
                        }
            except Exception:
                pass

    # 2. Simulated Telemetry (realistic variations)
    t = time.time()
    # Sinusoidal wave to create smooth realistic fluctuations
    temp_jitter = int(math.sin(t / 8.0) * 4)
    vram_jitter = int(math.cos(t / 12.0) * 180)
    fan_jitter = int(math.sin(t / 10.0) * 3)
    power_jitter = math.sin(t / 6.0) * 6.5
    util_jitter = int(math.sin(t / 5.0) * 8)

    base_temp = 46 + temp_jitter
    base_fan = 34 + fan_jitter
    base_vram = 3560 + vram_jitter
    total_vram = 12288
    base_power = round(52.4 + power_jitter, 1)
    base_util = max(5, 16 + util_jitter)

    return {
        "available": True,
        "simulated": True,
        "name": "NVIDIA GeForce RTX 4070 Ti (Simüle)",
        "temp": base_temp,
        "fan": base_fan,
        "vram_used": base_vram,
        "vram_total": total_vram,
        "power": base_power,
        "utilization": base_util,
        "driver": "550.54.14",
    }


def get_ai_stack_status():
    """
    Detects installation status of CUDA Toolkit, cuDNN, and TensorRT.
    """
    status = {
        "cuda": {"installed": False, "version": None, "pkg": "nvidia-cuda-toolkit"},
        "cudnn": {"installed": False, "version": None, "pkg": "libcudnn8"},
        "tensorrt": {"installed": False, "version": None, "pkg": "tensorrt"},
    }

    # 1. CUDA
    nvcc = shutil.which("nvcc")
    if not nvcc:
        for path in ("/usr/local/cuda/bin/nvcc", "/usr/bin/nvcc"):
            if os.path.isfile(path) and os.access(path, os.X_OK):
                nvcc = path
                break

    if nvcc:
        status["cuda"]["installed"] = True
        try:
            out = subprocess.check_output([nvcc, "--version"], text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                if "release" in line:
                    parts = line.split("release")
                    if len(parts) > 1:
                        status["cuda"]["version"] = parts[1].split(",")[0].strip()
        except Exception:
            status["cuda"]["version"] = "12.x"

    # 2. cuDNN
    cudnn_paths = glob.glob("/usr/lib*/**/libcudnn.so*", recursive=True) + glob.glob("/usr/local/cuda*/**/libcudnn.so*", recursive=True)
    if cudnn_paths:
        status["cudnn"]["installed"] = True
        status["cudnn"]["version"] = "8.x / 9.x"

    # 3. TensorRT
    nvinfer_paths = glob.glob("/usr/lib*/**/libnvinfer.so*", recursive=True) + glob.glob("/usr/local/cuda*/**/libnvinfer.so*", recursive=True)
    if nvinfer_paths:
        status["tensorrt"]["installed"] = True
        status["tensorrt"]["version"] = "8.x / 10.x"

    return status


def get_fan_control_info():
    """
    Returns configured fan speed setting if any.
    """
    cache_path = "/var/cache/parslinux-nvi-fan-speed"
    val = None
    if os.path.isfile(cache_path):
        try:
            with open(cache_path, "r") as f:
                val = int(f.read().strip())
        except (ValueError, OSError):
            pass
    return {"custom_speed": val, "is_custom": val is not None}


def get_power_limit_info():
    """
    Returns power limit settings (min, max, target, default).
    """
    cache_path = "/var/cache/parslinux-nvi-power-limit"
    target = None
    if os.path.isfile(cache_path):
        try:
            with open(cache_path, "r") as f:
                target = int(f.read().strip())
        except (ValueError, OSError):
            pass
    return {
        "target_watts": target or 200,
        "default_watts": 220,
        "min_watts": 100,
        "max_watts": 350,
        "is_custom": target is not None,
    }


def get_game_offload_status():
    """
    Checks if global NVIDIA game offload environment config is active.
    """
    path = "/etc/environment.d/10-parslinux-nvidia-games.conf"
    return os.path.isfile(path)


def get_detected_game_launchers():
    """
    Detects gaming platforms on the system (Steam, Lutris, Heroic, Bottles).
    """
    launchers = []
    candidates = [
        {"id": "steam", "name": "Steam", "icon": "steam", "bin": "steam"},
        {"id": "lutris", "name": "Lutris", "icon": "lutris", "bin": "lutris"},
        {"id": "heroic", "name": "Heroic Games Launcher", "icon": "heroic", "bin": "heroic"},
        {"id": "bottles", "name": "Bottles (Şişeler)", "icon": "com.usebottles.bottles", "bin": "bottles"},
    ]
    for c in candidates:
        installed = bool(shutil.which(c["bin"]))
        if not installed:
            # Check Flatpak
            try:
                out = subprocess.check_output(["flatpak", "list", "--app"], text=True, stderr=subprocess.DEVNULL)
                if c["id"] in out.lower():
                    installed = True
            except Exception:
                pass
        launchers.append({
            "id": c["id"],
            "name": c["name"],
            "installed": installed,
            "bin": c["bin"],
        })
    return launchers


def get_mangohud_status():
    """
    Returns MangoHud status: installed, enabled, config_path.
    """
    installed = bool(shutil.which("mangohud"))
    conf_path = os.path.expanduser("~/.config/MangoHud/MangoHud.conf")
    enabled = os.path.isfile(conf_path)
    return {
        "installed": installed,
        "enabled": enabled,
        "conf_path": conf_path,
    }


def set_mangohud_profile(enabled: bool):
    """
    Enables or disables ParsLinux custom gaming HUD profile for MangoHud.
    """
    conf_dir = os.path.expanduser("~/.config/MangoHud")
    conf_path = os.path.join(conf_dir, "MangoHud.conf")
    if enabled:
        os.makedirs(conf_dir, exist_ok=True)
        content = (
            "### ParsLinux Gaming HUD Profile ###\n"
            "fps\n"
            "fps_limit=0\n"
            "gpu_stats\n"
            "gpu_temp\n"
            "gpu_core_clock\n"
            "gpu_mem_clock\n"
            "gpu_power\n"
            "vram\n"
            "cpu_stats\n"
            "cpu_temp\n"
            "ram\n"
            "frame_timing=1\n"
            "gamemode\n"
            "position=top-left\n"
            "round_corners=8\n"
            "background_alpha=0.65\n"
            "font_size=20\n"
            "toggle_hud=Shift_R+F12\n"
        )
        try:
            with open(conf_path, "w") as f:
                f.write(content)
            return True
        except OSError:
            return False
    else:
        if os.path.isfile(conf_path):
            try:
                os.remove(conf_path)
            except OSError:
                pass
        return True


def _read_cache_int(filename: str) -> int:
    for candidate in (
        os.path.join("/var/cache", filename),
        os.path.expanduser(f"~/.cache/parslinux-nvidia-installer/{filename}"),
    ):
        if os.path.isfile(candidate):
            try:
                with open(candidate, "r") as f:
                    return int(f.read().strip())
            except (ValueError, OSError):
                pass
    return 0


def get_overclock_settings():
    """
    Returns configured GPU core and memory clock offsets (MHz).
    """
    core = _read_cache_int("parslinux-nvi-oc-core")
    mem = _read_cache_int("parslinux-nvi-oc-mem")
    return {
        "core_offset": core,
        "mem_offset": mem,
        "is_active": core != 0 or mem != 0,
    }


def is_timeshift_installed():
    """
    Checks if Timeshift system backup utility is available.
    """
    return bool(shutil.which("timeshift"))

