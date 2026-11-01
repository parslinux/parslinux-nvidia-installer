#!/usr/bin/env bash
# ==============================================================================
# ParsLinux Nvidia Installer - Master Management Script
# ==============================================================================
set -e

RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
CYAN=$'\033[0;36m'
MAGENTA=$'\033[0;35m'
BOLD=$'\033[1m'
NC=$'\033[0m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

show_header() {
    clear 2>/dev/null || true
    echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}${BOLD}║        ParsLinux Nvidia Installer — Control Panel            ║${NC}"
    echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

show_cli_help() {
    echo -e "Usage: ${BOLD}./manage.sh [COMMAND] [OPTIONS]${NC}"
    echo ""
    echo "Commands:"
    echo "  ${GREEN}run${NC}       [options]      Run the application (Development / Local)"
    echo "  ${GREEN}debug${NC}                    Run directly in simulated debug mode"
    echo "  ${RED}stop${NC}                     Terminate all running application processes"
    echo "  ${BLUE}install${NC}   [options]      Install distro dependencies and app to system"
    echo "  ${YELLOW}uninstall${NC} [options]      Completely remove the application from system"
    echo "  ${MAGENTA}package${NC}   [options]      Build .deb or .pkg.tar.zst packages"
    echo "  ${CYAN}test${NC}                      Run full automated unit and integration tests"
    echo "  ${BOLD}menu${NC}                      Open interactive terminal menu (default)"
}

ACTION="$1"
if [ -n "$ACTION" ]; then
    shift
    case "$ACTION" in
        run|calistir)
            exec ./run.sh "$@"
            ;;
        debug)
            exec ./run.sh --debug "$@"
            ;;
        stop|durdur|kill)
            exec ./stop.sh "$@"
            ;;
        install|kur)
            exec ./install.sh "$@"
            ;;
        uninstall|kaldir)
            exec ./uninstall.sh "$@"
            ;;
        package|paketle)
            exec ./package.sh "$@"
            ;;
        detect|algila|tara)
            exec ./run.sh --detect "$@"
            ;;
        test|testler)
            exec python3 -m unittest discover -s tests -p "test_*.py" -v
            ;;
        -h|--help|help|yardim)
            show_cli_help
            exit 0
            ;;
        menu)
            # Proceed to menu
            ;;
        *)
            echo -e "${RED}Unknown command: $ACTION${NC}"
            show_cli_help
            exit 1
            ;;
    esac
fi

while true; do
    show_header
    echo -e "${BOLD}Select an action:${NC}"
    echo -e "  ${GREEN}1)${NC} Run Application (Development Mode)"
    echo -e "  ${GREEN}2)${NC} Run Application (Simulated / Debug Mode)"
    echo -e "  ${CYAN}3)${NC} Run Automated Test Suite"
    echo -e "  ${MAGENTA}4)${NC} Build Packages (.deb / .pkg.tar.zst)"
    echo -e "  ${BLUE}5)${NC} Install to System"
    echo -e "  ${YELLOW}6)${NC} Uninstall from System"
    echo -e "  ${RED}7)${NC} Stop Running Processes"
    echo -e "  ${BOLD}8)${NC} Update Translations (.po / .mo)"
    echo -e "  ${BOLD}q)${NC} Quit"
    echo ""
    read -rp "Your choice [1-8, q]: " CHOICE

    case "$CHOICE" in
        1)
            ./run.sh
            read -rp "Press Enter to return to menu..."
            ;;
        2)
            ./run.sh --debug
            read -rp "Press Enter to return to menu..."
            ;;
        3)
            python3 -m unittest discover -s tests -p "test_*.py" -v || true
            read -rp "Press Enter to return to menu..."
            ;;
        4)
            ./package.sh
            read -rp "Press Enter to return to menu..."
            ;;
        5)
            ./install.sh
            read -rp "Press Enter to return to menu..."
            ;;
        6)
            ./uninstall.sh
            read -rp "Press Enter to return to menu..."
            ;;
        7)
            ./stop.sh
            read -rp "Press Enter to return to menu..."
            ;;
        8)
            ./update_translations.sh
            read -rp "Press Enter to return to menu..."
            ;;
        q|Q|exit)
            echo -e "${GREEN}Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid selection.${NC}"
            sleep 1
            ;;
    esac
done
