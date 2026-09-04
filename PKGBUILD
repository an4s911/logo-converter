# Maintainer: Anas Bashir <nasbas23@gmail.com>

pkgname=logo-converter
pkgver=1.1.0
pkgrel=1
pkgdesc="CLI tool to convert raster logos into scalable vector SVGs, multi-resolution PNGs, and favicon suites"
arch=('any')
license=('MIT')
provides=('convert-logo')
conflicts=('convert-logo')
depends=(
    'python'
    'python-pillow'
    'potrace'
    'librsvg'
    'inkscape'
)
optdepends=(
    'imagemagick: fallback raster conversion and ICO packaging'
)
source=(
    'convert_logo.py'
    'README.md'
    'LICENSE'
)
sha256sums=(
    '54f3f10df803eff0c651e8160b210cd8049ff14b021151ccfcad44d72e463350'
    'SKIP'
    'SKIP'
)

package() {
    # Install main executable with alias
    install -Dm755 "${srcdir}/convert_logo.py" "${pkgdir}/usr/bin/convert-logo"
    ln -s convert-logo "${pkgdir}/usr/bin/convert_logo"

    # Install documentation
    install -Dm644 "${srcdir}/README.md" "${pkgdir}/usr/share/doc/${pkgname}/README.md"

    # Install license
    install -Dm644 "${srcdir}/LICENSE" "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
}
