# Maintainer: ParsLinux Developers <dev@parslinux.org>
pkgname=parslinux-nvidia-installer
pkgver=1.0.0
pkgrel=1
pkgdesc="ParsLinux NVIDIA Graphics Driver Installer and Hybrid GPU Manager"
arch=('any')
url="https://parslinux.org"
license=('GPL-3.0-or-later')
depends=(
    'python'
    'python-gobject'
    'gtk4'
    'vte4'
    'polkit'
    'hwdata'
    'gnupg'
)
optdepends=(
    'nvidia-dkms: NVIDIA proprietary kernel module'
    'nvidia-utils: NVIDIA user-space tools and libraries'
    'opencl-nvidia: NVIDIA OpenCL implementation'
    'optimus-manager: Hybrid GPU switching support'
)
makedepends=(
    'python-setuptools'
    'gettext'
)

build() {
    cd "$srcdir/$pkgname-$pkgver" 2>/dev/null || cd "$startdir"
    python3 setup.py build
}

package() {
    cd "$srcdir/$pkgname-$pkgver" 2>/dev/null || cd "$startdir"
    python3 setup.py install --root="$pkgdir" --prefix=/usr --optimize=1
}
