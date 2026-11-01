#!/usr/bin/env bash
# ==============================================================================
# ParsLinux Nvidia Installer - System Installation Script
# ==============================================================================
set -e

RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
CYAN=$'\033[0;36m'
BOLD=$'\033[1m'
NC=$'\033[0m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo -e "${CYAN}${BOLD}=== ParsLinux Nvidia Installer — Installer ===${NC}"

show_help() {
    echo -e "Usage: ${BOLD}./install.sh [OPTIONS]${NC}"
    echo ""
    echo "Options:"
    echo "  -h, --help       Show this help manual"
    echo "  --no-deps        Skip package manager dependency installation"
    echo "  --deps-only      Only install system dependencies, do not install the app"
    echo ""
    echo "Examples:"
    echo "  ./install.sh             # Full automated dependencies and app installation"
    echo "  ./install.sh --no-deps   # Install app directly without checking dependencies"
    echo "  ./install.sh --deps-only # Only install prerequisite distro packages"
}

NO_DEPS=false
DEPS_ONLY=false

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            show_help
            exit 0
            ;;
        --no-deps)
            NO_DEPS=true
            ;;
        --deps-only)
            DEPS_ONLY=true
            ;;
        *)
            echo -e "${RED}Unknown option: $arg${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Install distribution dependencies
if [ "$NO_DEPS" = false ]; then
    echo -e "${BLUE}▶ Detecting system package manager and installing dependencies...${NC}"
    if command -v apt-get &>/dev/null; then
        echo -e "${GREEN}Detected APT (Debian/Ubuntu/ParsLinux)...${NC}"
        sudo apt-get update -y
        sudo apt-get install -y \
            python3 \
            python3-gi \
            gir1.2-gtk-4.0 \
            gir1.2-vte-3.91 \
            gir1.2-polkit-1.0 \
            python3-apt \
            pciutils \
            gnupg \
            gettext
    elif command -v pacman &>/dev/null; then
        echo -e "${GREEN}Detected Pacman (Arch Linux / CachyOS / ParsLinux Arch)...${NC}"
        sudo pacman -S --needed --noconfirm \
            python \
            python-gobject \
            gtk4 \
            vte4 \
            polkit \
            hwdata \
            gnupg \
            gettext \
            python-setuptools
    else
        echo -e "${YELLOW}Unknown package manager. Please ensure Python 3, GTK 4, VTE 4, and Polkit are installed.${NC}"
    fi
fi

if [ "$DEPS_ONLY" = true ]; then
    echo -e "${GREEN}✓ Dependencies installed successfully. Skipping app installation (--deps-only).${NC}"
    exit 0
fi

echo -e "${BLUE}▶ Building localization and installing files...${NC}"
./update_translations.sh 2>/dev/null || true

# Execute setup.py install
echo -e "${BLUE}▶ Installing ParsLinux Nvidia Installer to system...${NC}"
sudo python3 setup.py install --root=/ --prefix=/usr --optimize=1

# Reload systemd and desktop database
echo -e "${BLUE}▶ Updating desktop and systemd caches...${NC}"
sudo update-desktop-database -q /usr/share/applications 2>/dev/null || true
sudo systemctl daemon-reload 2>/dev/null || true

echo -e "${GREEN}${BOLD}✓ ParsLinux Nvidia Installer installed successfully!${NC}"
echo -e "You can now run it from your application menu or via command line:"
echo -e "  ${BOLD}parslinux-nvidia-installer${NC}"
