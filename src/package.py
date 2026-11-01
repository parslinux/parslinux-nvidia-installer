#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ParsLinux Nvidia Installer - Privileged Package & Hardware Management Helper
Executed directly or via PolicyKit (pkexec) to manage drivers and system services.
"""

import os
import re
import sys
import shutil
import subprocess

try:
    import apt  # type: ignore
    import apt_pkg  # type: ignore
    apt_pkg.init_system()
    HAS_APT = True
except (ImportError, AttributeError):
    HAS_APT = False
    apt = None
    apt_pkg = None

os.environ["DEBIAN_FRONTEND"] = "noninteractive"
nouveau = "xserver-xorg-video-nouveau"

nvidia_modprobe_conf = "/etc/modprobe.d/nvidia.conf"
nvidia_modprobed_conf = "/etc/modprobe.d/nvidia.conf.bak"
nouveau_modprobe_conf = "/etc/modprobe.d/nvidia-blacklists-nouveau.conf"
nouveau_modprobed_conf = "/etc/modprobe.d/nvidia-blacklists-nouveau.conf.bak"

# Primary and legacy GPU disable markers
nvidia_disable_gpu_path = "/var/cache/parslinux-nvi-disable-gpu"
legacy_disable_gpu_path = "/var/cache/pni-disable-gpu"

pci_rescan_path = "/sys/bus/pci/rescan"
dest = "/etc/apt/sources.list.d/nvidia-drivers.list"

# Keyring location and armored public key source
nvidia_keyring = "/usr/share/keyrings/nvidia-drivers.gpg"
nvidia_pub_src = os.path.normpath(os.path.join(os.path.dirname(__file__), "../nvidia.pub"))

cuda_repo_base = "https://developer.download.nvidia.com/compute/cuda/repos"

# NVIDIA CUDA repository signing keys:
#   debian12 -> "cudatools" (A4B469963BF863CC, SHA1)
#   debian13 -> "Kitmaker (Debian 13 ...)" (97A5D4CB8793F200, SHA256)
_CUDA_REPO_KEY_FPR = {
    "debian12": "EB693B3035CD5710E231E123A4B469963BF863CC",
    "debian13": "02182E60104FCDC26EAE1B8597A5D4CB8793F200",
}

_SUPPORTED_CUDA_MAJORS = tuple(
    sorted(int(d[len("debian"):]) for d in _CUDA_REPO_KEY_FPR)
)

_DEBIAN_CODENAME_MAJOR = {
    "bullseye": 11,
    "bookworm": 12,
    "trixie": 13,
    "forky": 14,
    "sid": 13,
}

REBOOT_MARKERS = [
    "/run/parslinux-nvi.reboot",
    "/run/pardus-nvi.reboot",
]


def readfile(filepath):
    if not os.path.isfile(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return None


def sys_source():
    return os.path.isfile(dest)


def _debian_major():
    """
    Detect Debian base version.
    Supports ParsLinux, Debian, Pardus, Ubuntu and derivative os-release fields.
    """
    # 1. Check /etc/parslinux_version if present
    parslinux_ver = readfile("/etc/parslinux_version")
    if parslinux_ver:
        m = re.match(r"^(\d+)", parslinux_ver)
        if m:
            return 12  # ParsLinux 1.0 is based on Debian 12/13 series

    # 2. Check /etc/debian_version
    raw = readfile("/etc/debian_version")
    if raw:
        m = re.match(r"^(\d+)", raw)
        if m:
            return int(m.group(1))
        codename = raw.split("/", 1)[0].strip().lower()
        major = _DEBIAN_CODENAME_MAJOR.get(codename)
        if major:
            return major

    # 3. Check /etc/os-release or /usr/lib/os-release
    for path in ("/etc/os-release", "/usr/lib/os-release"):
        content = readfile(path)
        if not content:
            continue
        env_dict = {}
        for line in content.splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env_dict[k.strip()] = v.strip().strip('"').strip("'")
        
        # Check DEBIAN_CODENAME, VERSION_CODENAME
        for key in ("DEBIAN_CODENAME", "VERSION_CODENAME", "UBUNTU_CODENAME"):
            if key in env_dict:
                cname = env_dict[key].lower()
                if cname in _DEBIAN_CODENAME_MAJOR:
                    return _DEBIAN_CODENAME_MAJOR[cname]

        # Check VERSION_ID
        if "VERSION_ID" in env_dict:
            m = re.match(r"^(\d+)", env_dict["VERSION_ID"])
            if m:
                val = int(m.group(1))
                if val in (11, 12, 13, 14):
                    return val

    # Default to newest supported release (e.g. 13)
    return _SUPPORTED_CUDA_MAJORS[-1]


def cuda_repo_distro():
    major = _debian_major()
    if major is None:
        major = _SUPPORTED_CUDA_MAJORS[-1]
    elif major < _SUPPORTED_CUDA_MAJORS[0]:
        major = _SUPPORTED_CUDA_MAJORS[0]
    elif major > _SUPPORTED_CUDA_MAJORS[-1]:
        major = _SUPPORTED_CUDA_MAJORS[-1]
    return f"debian{major}"


def _nvidia_source_line(distro=None):
    if distro is None:
        distro = cuda_repo_distro()
    return f"deb [signed-by={nvidia_keyring}] {cuda_repo_base}/{distro}/x86_64/ /\n"


def _keyring_has_fingerprint(keyring, fingerprint):
    if not os.path.isfile(keyring):
        return False
    try:
        out = subprocess.run(
            ["gpg", "--no-default-keyring", "--show-keys",
             "--with-colons", "--with-fingerprint", keyring],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        ).stdout.decode("utf-8", "replace")
    except (OSError, ValueError):
        return False
    for line in out.splitlines():
        parts = line.split(":")
        if parts and parts[0] == "fpr" and len(parts) >= 10:
            if parts[9].upper() == fingerprint.upper():
                return True
    return False


def _build_keyring_from_pub():
    if not os.path.isfile(nvidia_pub_src):
        print(f"ensure_keyring: armored key source missing: {nvidia_pub_src}", file=sys.stderr)
        return False
    try:
        with open(nvidia_pub_src, "rb") as src:
            proc = subprocess.run(
                ["gpg", "--dearmor"],
                stdin=src, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        if proc.returncode != 0 or not proc.stdout:
            print(f"ensure_keyring: gpg --dearmor failed: {proc.stderr.decode('utf-8', 'replace').strip()}", file=sys.stderr)
            return False
        os.makedirs(os.path.dirname(nvidia_keyring), exist_ok=True)
        tmp = nvidia_keyring + ".tmp"
        with open(tmp, "wb") as out:
            out.write(proc.stdout)
        os.chmod(tmp, 0o644)
        os.replace(tmp, nvidia_keyring)
        return True
    except OSError as e:
        print(f"ensure_keyring: failed to build {nvidia_keyring}: {e}", file=sys.stderr)
        return False


def ensure_keyring(distro):
    fpr = _CUDA_REPO_KEY_FPR.get(distro)
    if fpr is None:
        return True
    if _keyring_has_fingerprint(nvidia_keyring, fpr):
        return True
    if not _build_keyring_from_pub():
        return False
    return _keyring_has_fingerprint(nvidia_keyring, fpr)


def mark_need_reboot():
    for path in REBOOT_MARKERS:
        try:
            with open(path, "w") as f:
                f.write("1")
        except OSError:
            pass


def move_conf_if_dest_absent(src, dst):
    if not (os.path.isfile(src) and not os.path.isfile(dst)):
        return False
    try:
        os.replace(src, dst)
        return True
    except OSError as e:
        print(f"move_conf: failed to move {src} -> {dst}: {e}", file=sys.stderr)
        return False


def disable_sec_gpu():
    changed = False
    for path in (nvidia_disable_gpu_path, legacy_disable_gpu_path):
        if not os.path.isfile(path):
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:
                    f.write("Secondary GPU Disabled by ParsLinux Nvidia Installer\n")
                changed = True
            except OSError:
                pass

    if move_conf_if_dest_absent(nvidia_modprobe_conf, nvidia_modprobed_conf):
        changed = True
    if move_conf_if_dest_absent(nouveau_modprobe_conf, nouveau_modprobed_conf):
        changed = True
    if changed:
        mark_need_reboot()
    return True


def rescan_pci():
    try:
        if os.path.exists(pci_rescan_path):
            with open(pci_rescan_path, "w") as f:
                f.write("1")
    except OSError as e:
        print(f"enable_sec_gpu: pci rescan failed: {e}", file=sys.stderr)


def enable_sec_gpu():
    changed = False
    for path in (nvidia_disable_gpu_path, legacy_disable_gpu_path):
        if os.path.isfile(path):
            try:
                os.remove(path)
                changed = True
            except OSError:
                pass

    if move_conf_if_dest_absent(nvidia_modprobed_conf, nvidia_modprobe_conf):
        changed = True
    if move_conf_if_dest_absent(nouveau_modprobed_conf, nouveau_modprobe_conf):
        changed = True
    rescan_pci()
    if changed:
        mark_need_reboot()
    return True


def check_sec_state():
    return not (os.path.isfile(nvidia_disable_gpu_path) or os.path.isfile(legacy_disable_gpu_path))


_NVIDIA_EXTRA_PKGS = (
    "xserver-xorg-video-nvidia",
    "libgl1-nvidia-glvnd-glx",
    "glx-alternative-nvidia",
    "mangohud",
    "timeshift",
    "goverlay",
)

_LINUX_HEADERS_RE = re.compile(r"^linux-headers-[a-zA-Z0-9._+-]+$")
_NVIDIA_DRIVER_RE = re.compile(r"^nvidia-[a-zA-Z0-9_-]+$")
_AI_DEV_RE = re.compile(r"^(libcudnn[0-9]*(-dev)?|libnvinfer[0-9]*(-dev)?|tensorrt[a-zA-Z0-9_-]*|nvidia-prime)$")
_VERSION_RE = re.compile(r"^[0-9][A-Za-z0-9.+~:-]*$")


def _split_pkg(arg):
    name, sep, ver = arg.partition("=")
    return (name, ver) if sep else (name, None)


def _is_allowed_package(name):
    if not name or len(name) > 100 or name.startswith("-"):
        return False
    pkg, sep, ver = name.partition("=")
    if sep:
        if not ver or not _VERSION_RE.match(ver):
            return False
        return bool(
            _NVIDIA_DRIVER_RE.match(pkg)
            or _AI_DEV_RE.match(pkg)
            or _LINUX_HEADERS_RE.match(pkg)
            or pkg in _NVIDIA_EXTRA_PKGS
        )
    if name == nouveau or name in _NVIDIA_EXTRA_PKGS:
        return True
    if _LINUX_HEADERS_RE.match(name) or _NVIDIA_DRIVER_RE.match(name) or _AI_DEV_RE.match(name):
        return True
    return False


def _nvidia_stack_realign(driver, pinned_version=None):
    if not HAS_APT:
        return [], []
    try:
        cache = apt.Cache()
    except Exception as e:
        print(f"install_nvidia: could not open apt cache: {e}", file=sys.stderr)
        return [], []
    if driver not in cache:
        return [], []
    if pinned_version:
        target = pinned_version
    else:
        candidate = cache[driver].candidate
        if candidate is None:
            return [], []
        target = candidate.version
    pins, removals = [], []
    for pkg in cache:
        try:
            if not pkg.is_installed or pkg.name == driver:
                continue
            installed = pkg.installed
            source = (installed.source_name or "") if installed else ""
            if not source.startswith("nvidia-graphics-drivers"):
                continue
            if installed.version == target:
                continue
            if any(v.version == target for v in pkg.versions):
                pins.append(f"{pkg.name}={target}")
            else:
                removals.append(f"{pkg.name}-")
        except Exception:
            continue
    return pins, removals


def install_nvidia(packages):
    if not packages:
        print("install_nvidia: no packages provided, aborting", file=sys.stderr)
        return False
    for pkg in packages:
        if not _is_allowed_package(pkg):
            print(f"install_nvidia: refusing unsafe package name: {pkg!r}", file=sys.stderr)
            return False

    print("Updating package lists...")
    if subprocess.call(
        ["apt-get", "update", "-yq", "-o", "APT::Update::Error-Mode=any"],
        env={**os.environ},
    ) != 0:
        print("Warning: apt-get update returned non-zero, continuing...")

    driver_spec = next((p for p in packages if p.startswith("nvidia-")), None)
    pins, removals = [], []
    if driver_spec:
        driver_name, pinned = _split_pkg(driver_spec)
        pins, removals = _nvidia_stack_realign(driver_name, pinned)

    cmds = [
        ["apt-get", "install", "-yq", "--allow-downgrades", "--",
         *packages, *pins, *removals],
        ["apt-get", "autoremove", "-yq"],
    ]
    for cmd in cmds:
        print(f"Executing: {' '.join(cmd)}")
        rc = subprocess.call(cmd, env={**os.environ})
        if rc != 0:
            return False
    mark_need_reboot()
    return True


def _nvidia_stack_packages():
    if not HAS_APT:
        return []
    try:
        cache = apt.Cache()
    except Exception as e:
        print(f"install_nouveau: failed to open apt cache: {e}", file=sys.stderr)
        return []
    names = []
    for pkg in cache:
        try:
            if not pkg.is_installed:
                continue
            installed = pkg.installed
            source = (installed.source_name or "") if installed else ""
            if (pkg.name.startswith("nvidia-")
                    or source.startswith("nvidia-graphics-drivers")
                    or pkg.name in _NVIDIA_EXTRA_PKGS):
                names.append(pkg.name)
        except Exception:
            continue
    return names


def restore_modprobe_baks_if_enabled():
    if os.path.isfile(nvidia_disable_gpu_path) or os.path.isfile(legacy_disable_gpu_path):
        return
    move_conf_if_dest_absent(nvidia_modprobed_conf, nvidia_modprobe_conf)
    move_conf_if_dest_absent(nouveau_modprobed_conf, nouveau_modprobe_conf)


def install_nouveau():
    restore_modprobe_baks_if_enabled()
    nvidia_pkgs = _nvidia_stack_packages()

    cmds = []
    if nvidia_pkgs:
        cmds.append(["apt-get", "purge", "-yq", *nvidia_pkgs])
    cmds.append(["apt-get", "autoremove", "-yq"])
    cmds.append(["apt-get", "install", "-yq", nouveau])

    for cmd in cmds:
        print(f"Executing: {' '.join(cmd)}")
        rc = subprocess.call(cmd, env={**os.environ})
        if rc != 0:
            return False
    mark_need_reboot()
    return True


def update():
    backup = dest + ".prev"
    had = os.path.isfile(dest)
    try:
        if had:
            os.replace(dest, backup)
        else:
            distro = cuda_repo_distro()
            if not ensure_keyring(distro):
                raise RuntimeError(f"missing signing key for {distro} repo")
            tmp = dest + ".tmp"
            with open(tmp, "w") as f:
                f.write(_nvidia_source_line(distro))
            os.replace(tmp, dest)

        rc = subprocess.call(
            ["apt-get", "update", "-yq", "-o", "APT::Update::Error-Mode=any"],
            env={**os.environ},
        )
        if rc != 0:
            raise RuntimeError(f"apt update failed with rc={rc}")

        if had and os.path.isfile(backup):
            os.remove(backup)
        return True

    except Exception as e:
        print(f"update: rolling back due to error: {e}", file=sys.stderr)
        if had:
            if os.path.isfile(backup):
                os.replace(backup, dest)
        else:
            if os.path.isfile(dest):
                os.remove(dest)
        return False


def get_pkg_info(package_name: str):
    if not HAS_APT:
        return {"ver": "1.0.0", "name": package_name}
    cache = apt.Cache()
    if package_name not in cache:
        return {"ver": "unknown", "name": package_name}
    pkg = cache[package_name]
    if pkg.is_installed:
        version = pkg.installed.version
        name = pkg.installed.summary
    else:
        version = pkg.versions[0].version if pkg.versions else "unknown"
        name = pkg.versions[0].summary if pkg.versions else package_name

    return {"ver": version, "name": name}


prime_mode_path = "/var/cache/parslinux-nvi-prime-mode"


def set_prime_mode(mode: str):
    """
    Sets PRIME power profile:
    - 'integrated': Power down secondary GPU and switch to iGPU.
    - 'on-demand': Enable secondary GPU with NVIDIA PRIME Render Offload.
    - 'nvidia': Enable secondary GPU with performance rendering.
    """
    valid_modes = ("integrated", "on-demand", "nvidia")
    if mode not in valid_modes:
        print(f"set_prime_mode: invalid mode '{mode}'. Expected one of {valid_modes}", file=sys.stderr)
        return False

    try:
        os.makedirs(os.path.dirname(prime_mode_path), exist_ok=True)
        with open(prime_mode_path, "w") as f:
            f.write(mode + "\n")
    except OSError as e:
        print(f"set_prime_mode: failed to save state file: {e}", file=sys.stderr)

    changed = False
    if mode == "integrated":
        changed = disable_sec_gpu()
        prime_select = shutil_which("prime-select")
        if prime_select:
            try:
                subprocess.call([prime_select, "intel"])
            except Exception:
                pass
    else:
        changed = enable_sec_gpu()
        prime_select = shutil_which("prime-select")
        if prime_select:
            try:
                subprocess.call([prime_select, mode])
            except Exception:
                pass

    if changed:
        mark_need_reboot()
    print(f"PRIME profile set to: {mode}")
    return True


def shutil_which(cmd):
    return shutil.which(cmd)


def install_ai_tools(requested_pkgs=None):
    """
    Installs CUDA Toolkit and optional deep learning libraries (cuDNN, TensorRT).
    """
    if not requested_pkgs:
        requested_pkgs = ["nvidia-cuda-toolkit"]

    # Validate all packages against security whitelist
    for p in requested_pkgs:
        if not _is_allowed_package(p):
            print(f"install_ai_tools: package '{p}' rejected by security policy", file=sys.stderr)
            return False

    cmd = ["apt-get", "install", "-yq", "--install-recommends"] + list(requested_pkgs)
    print(f"Executing: {' '.join(cmd)}")
    rc = subprocess.call(cmd, env={**os.environ})
    if rc == 0:
        mark_need_reboot()
        return True
    return False


def _get_cache_path(filename: str) -> str:
    try:
        if os.access("/var/cache", os.W_OK):
            return os.path.join("/var/cache", filename)
    except Exception:
        pass
    user_cache = os.path.expanduser("~/.cache/parslinux-nvidia-installer")
    os.makedirs(user_cache, exist_ok=True)
    return os.path.join(user_cache, filename)


FAN_SPEED_CACHE = "/var/cache/parslinux-nvi-fan-speed"
POWER_LIMIT_CACHE = "/var/cache/parslinux-nvi-power-limit"
GAME_OFFLOAD_CONF = "/etc/environment.d/10-parslinux-nvidia-games.conf"


def set_fan_speed(percent: int):
    try:
        val = int(percent)
        if not (0 <= val <= 100):
            print("set_fan_speed: percent must be 0..100", file=sys.stderr)
            return False
    except (ValueError, TypeError):
        return False

    cache_path = _get_cache_path("parslinux-nvi-fan-speed")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w") as f:
        f.write(str(val) + "\n")

    settings_bin = shutil_which("nvidia-settings")
    if settings_bin:
        try:
            subprocess.call([
                settings_bin,
                "-a", "[gpu:0]/GPUFanControlState=1",
                "-a", f"[fan:0]/GPUTargetFanSpeed={val}"
            ])
        except Exception:
            pass
    print(f"Fan speed set to {val}%")
    return True


def set_power_limit(watts: int):
    try:
        val = int(watts)
        if not (50 <= val <= 600):
            print("set_power_limit: watts must be 50..600", file=sys.stderr)
            return False
    except (ValueError, TypeError):
        return False

    cache_path = _get_cache_path("parslinux-nvi-power-limit")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w") as f:
        f.write(str(val) + "\n")

    smi_bin = shutil_which("nvidia-smi")
    if smi_bin:
        try:
            rc = subprocess.call([smi_bin, "-pl", str(val)])
            if rc != 0:
                print("nvidia-smi power limit failed, cache updated", file=sys.stderr)
        except Exception:
            pass
    print(f"Power limit set to {val}W")
    return True


def set_game_offload(state: str):
    enable = str(state).lower() in ("1", "true", "on", "enable")
    os.makedirs(os.path.dirname(GAME_OFFLOAD_CONF), exist_ok=True)
    if enable:
        content = (
            "__NV_PRIME_RENDER_OFFLOAD=1\n"
            "__GLX_VENDOR_LIBRARY_NAME=nvidia\n"
            "__VK_LAYER_NV_optimus=NVIDIA_only\n"
        )
        with open(GAME_OFFLOAD_CONF, "w") as f:
            f.write(content)
        print("Automatic NVIDIA game offload enabled in /etc/environment.d")
    else:
        if os.path.isfile(GAME_OFFLOAD_CONF):
            try:
                os.remove(GAME_OFFLOAD_CONF)
            except OSError:
                pass
        print("Automatic NVIDIA game offload disabled")
    return True


def set_gpu_overclock(core_offset: int, mem_offset: int):
    """
    Sets GPU core clock and memory transfer rate offsets (MHz).
    Safe ranges:
    - Core offset: -300 to +400 MHz
    - Memory offset: -1000 to +2000 MHz
    """
    try:
        core_offset = int(core_offset)
        mem_offset = int(mem_offset)
    except (ValueError, TypeError):
        print("set_gpu_overclock: offsets must be integers", file=sys.stderr)
        return False

    if not (-300 <= core_offset <= 400):
        print(f"set_gpu_overclock: core offset {core_offset} out of safe range [-300..400]", file=sys.stderr)
        return False

    if not (-1000 <= mem_offset <= 2000):
        print(f"set_gpu_overclock: memory offset {mem_offset} out of safe range [-1000..2000]", file=sys.stderr)
        return False

    core_path = _get_cache_path("parslinux-nvi-oc-core")
    mem_path = _get_cache_path("parslinux-nvi-oc-mem")
    try:
        with open(core_path, "w") as f:
            f.write(str(core_offset))
        with open(mem_path, "w") as f:
            f.write(str(mem_offset))
    except OSError as e:
        print(f"set_gpu_overclock cache write failed: {e}", file=sys.stderr)

    # Apply via nvidia-settings if available and display accessible
    if shutil.which("nvidia-settings"):
        env = os.environ.copy()
        if "DISPLAY" not in env:
            env["DISPLAY"] = ":0"
        try:
            subprocess.call(
                ["nvidia-settings", "-a", f"[gpu:0]/GPUGraphicsClockOffsetAllPerformanceLevels={core_offset}"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.call(
                ["nvidia-settings", "-a", f"[gpu:0]/GPUMemoryTransferRateOffsetAllPerformanceLevels={mem_offset}"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    print(f"GPU Overclock offsets applied: Core {core_offset:+d} MHz, Memory {mem_offset:+d} MHz")
    return True


def create_timeshift_snapshot(comment: str = "ParsLinux NVIDIA Driver Backup"):
    """
    Creates a system restore snapshot using Timeshift.
    """
    safe_comment = re.sub(r"[^a-zA-Z0-9 _.-]", "", str(comment))[:80].strip() or "ParsLinux NVIDIA Backup"
    timeshift_bin = shutil.which("timeshift") or "/usr/bin/timeshift"
    if not os.path.isfile(timeshift_bin):
        print("create_timeshift_snapshot: timeshift is not installed on system", file=sys.stderr)
        return False

    cmd = [timeshift_bin, "--create", "--comments", safe_comment, "--tags", "D"]
    print(f"Executing: {' '.join(cmd)}")
    rc = subprocess.call(cmd)
    return rc == 0


def install_extra_package(pkg_name: str):
    """
    Installs an authorized extra gaming/utility package (e.g. mangohud, timeshift).
    """
    if pkg_name not in _NVIDIA_EXTRA_PKGS:
        print(f"install_extra_package: package {pkg_name} is not whitelisted", file=sys.stderr)
        return False

    if HAS_APT or shutil.which("apt-get"):
        cmd = ["apt-get", "install", "-yq", "--", pkg_name]
    elif shutil.which("pacman"):
        cmd = ["pacman", "-S", "--needed", "--noconfirm", pkg_name]
    else:
        print("install_extra_package: no supported package manager found", file=sys.stderr)
        return False

    print(f"Executing: {' '.join(cmd)}")
    rc = subprocess.call(cmd)
    return rc == 0


if __name__ == "__main__":
    args = sys.argv
    if len(args) <= 1:
        print("Usage: package.py <command> [args...]", file=sys.stderr)
        sys.exit(2)

    param1 = args[1]
    if param1 in ("nouveau", nouveau, "install-nouveau"):
        ok = install_nouveau()
    elif param1 == "update":
        ok = update()
    elif param1 == "disable-sec-gpu":
        ok = disable_sec_gpu()
    elif param1 == "enable-sec-gpu":
        ok = enable_sec_gpu()
    elif param1 == "prime-mode":
        mode_arg = args[2] if len(args) > 2 else "on-demand"
        ok = set_prime_mode(mode_arg)
    elif param1 == "set-fan-speed":
        spd = int(args[2]) if len(args) > 2 else 50
        ok = set_fan_speed(spd)
    elif param1 == "set-power-limit":
        pwr = int(args[2]) if len(args) > 2 else 200
        ok = set_power_limit(pwr)
    elif param1 == "set-game-offload":
        st = args[2] if len(args) > 2 else "on"
        ok = set_game_offload(st)
    elif param1 == "set-overclock":
        c_off = int(args[2]) if len(args) > 2 else 0
        m_off = int(args[3]) if len(args) > 3 else 0
        ok = set_gpu_overclock(c_off, m_off)
    elif param1 == "create-snapshot":
        comment = args[2] if len(args) > 2 else "ParsLinux NVIDIA Driver Backup"
        ok = create_timeshift_snapshot(comment)
    elif param1 == "install-extra":
        pkg = args[2] if len(args) > 2 else "mangohud"
        ok = install_extra_package(pkg)
    elif param1 == "install-ai-tools":
        pkgs_arg = args[2:] if len(args) > 2 else ["nvidia-cuda-toolkit"]
        ok = install_ai_tools(pkgs_arg)
    elif param1 == "install-nvidia":
        ok = install_nvidia(args[2:])
    else:
        print(f"unknown subcommand: {param1}", file=sys.stderr)
        sys.exit(2)

    sys.exit(0 if ok else 1)
