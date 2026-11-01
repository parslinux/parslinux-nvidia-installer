#!/usr/bin/env bash
# ==============================================================================
# ParsLinux Nvidia Installer - Run Script
# ==============================================================================
set -e

# Color definitions
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
CYAN=$'\033[0;36m'
BOLD=$'\033[1m'
NC=$'\033[0m' # No Color

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo -e "${CYAN}${BOLD}=== ParsLinux Nvidia Installer — Launcher ===${NC}"

show_help() {
    echo -e "Usage: ${BOLD}./run.sh [OPTIONS]${NC}"
    echo ""
    echo "Options:"
    echo "  -h, --help       Show this help message"
    echo "  --detect, -d     Auto-detect graphics hardware and print diagnostic report"
    echo "  --debug, -g      Run in debug / simulated hardware mode"
    echo "  --system         Run system-installed version instead of local dev source"
    echo "  --test           Run automated test suite"
    echo "  -v, --version    Show version"
    echo ""
    echo "Examples:"
    echo "  ./run.sh                 # Auto-detects GPUs or falls back to debug on VM/non-Nvidia"
    echo "  ./run.sh --detect        # Auto-detect GPU hardware and print full report"
    echo "  ./run.sh --debug         # Force simulated NVIDIA RTX GPU for UI demonstration"
    echo "  ./run.sh --system        # Run installed system binary"
    echo "  ./run.sh --test          # Run automated tests"
}

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    show_help
    exit 0
fi

if [[ "$1" == "--detect" || "$1" == "-d" ]]; then
    shift
    exec ./parslinux-nvidia-installer --detect "$@"
fi

if [[ "$1" == "--test" ]]; then
    echo -e "${BLUE}▶ Launching test suite: tests/test_nvidia_installer.py...${NC}"
    exec python3 -m unittest discover -s tests -p "test_*.py" -v
fi

if [[ "$1" == "--system" ]]; then
    shift
    if ! command -v parslinux-nvidia-installer &>/dev/null; then
        echo -e "${RED}✗ Error: 'parslinux-nvidia-installer' is not installed on system!${NC}"
        echo -e "Install first using ${BOLD}./install.sh${NC} or run without --system for dev mode."
        exit 1
    fi
    echo -e "${GREEN}▶ Running system installed version...${NC}"
    exec parslinux-nvidia-installer "$@"
fi

# Check Python and GUI dependencies
echo -e "${BLUE}🔍 Checking environment and dependencies...${NC}"
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}✗ Error: python3 not found! Please install Python 3.${NC}"
    exit 1
fi

DEPS_CHECK=$(python3 -c "
import sys
missing = []
try:
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Vte', '2.91')
    from gi.repository import Gtk, Vte
except Exception as e:
    missing.append(f'PyGObject / GTK3 / VTE ({e})')

if missing:
    print('; '.join(missing))
    sys.exit(1)
sys.exit(0)
" 2>&1) || {
    echo -e "${RED}✗ Missing GUI dependencies:${NC} $DEPS_CHECK"
    echo -e "${YELLOW}Please install the required packages:${NC}"
    echo -e "  Debian/Ubuntu/Pars: ${BOLD}sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-vte-2.91 gir1.2-polkit-1.0 python3-apt pciutils gnupg${NC}"
    echo -e "  Arch/CachyOS:       ${BOLD}sudo pacman -S python-gobject gtk3 vte3 polkit hwdata gnupg${NC}"
    echo -e "  Or run:             ${BOLD}./install.sh${NC}"
    exit 1
}

echo -e "${GREEN}✓ Environment ready (Python 3, GTK 3, VTE).${NC}"

# If no NVIDIA card is present in hardware and not forced, default to debug mode so UI displays nicely
HAS_NVIDIA=$(lspci 2>/dev/null | grep -i "10de:\|nvidia" || true)
if [[ -z "$HAS_NVIDIA" && "$*" != *"--debug"* && "$*" != *"-g"* ]]; then
    echo -e "${YELLOW}ℹ No physical NVIDIA GPU found on this machine.${NC}"
    echo -e "${YELLOW}ℹ Activating simulated debug mode (PARSLINUX_NVI_DEBUG=1) for demonstration.${NC}"
    export PARSLINUX_NVI_DEBUG=1
fi

# Launch application from local source
echo -e "${GREEN}▶ Starting application (Local source: ./parslinux-nvidia-installer)...${NC}"
exec ./parslinux-nvidia-installer "$@"
