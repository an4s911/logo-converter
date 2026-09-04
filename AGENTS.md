# AGENTS.md

This file gives repository-wide instructions and technical guidelines for agents working on `logo-converter`.

## Project Overview

- `logo-converter` is a standalone, dependency-minimal CLI tool and Arch Linux package.
- It transforms raster logos (PNG, JPG, WebP) into a complete, production-ready brand suite:
  - Vector SVGs (Black, White, Primary, Gradient, CurrentColor, Dark/Light BG, Squircle, Padded variants).
  - Multi-resolution transparent PNGs (16x16 to 1024x1024).
  - Padded container PNGs and high-quality JPEGs (512x512, 1024x1024).
  - Production favicons (`favicon.ico` multi-res 16/32/48, `favicon.svg`, `apple-touch-icon.png`, `android-chrome-*.png`).
  - Web App Manifest (`site.webmanifest`).

## Toolchain & Dependencies

The converter orchestrates standard Linux/macOS graphics utilities:

| Tool | Role in Pipeline | Fallback / Notes |
|------|-------------------|------------------|
| `python-pillow` | Alpha thresholding, bbox extraction, multi-res ICO packaging | Automatically searches system `site-packages` if running inside an isolated venv. Falls back to `magick` if completely absent. |
| `potrace` | High-precision Bézier curve vectorization | Requires 1-bit monochrome PBM bitmap (`0` = mark, `255` = bg). |
| `inkscape` | Coordinate normalizer (`--export-plain-svg`) | Flattens matrix transforms and extracts pure `<path d="...">` strings. |
| `rsvg-convert` | High-fidelity SVG-to-PNG rasterizer | Renders all multi-resolution PNGs, favicons, and app icons. |
| `imagemagick` | Optional fallback | Used for alpha extraction, trim detection, and ICO building if Pillow is absent. |

## Asset Architecture & Framing Rules

The asset suite uses a dual-framing model to ensure logos look optimal in both standalone UI components and container icons:

### 1. Padded Container & Framed Assets
* **Files**: `logo-dark-bg.svg`, `logo-dark-bg-white.svg`, `logo-light-bg.svg`, `logo-squircle-dark.svg`, `logo-squircle-white.svg`, `logo-padded-*.svg`, `apple-touch-icon.png`, `android-chrome-*.png`, and container PNGs/JPGs.
* **Canvas & ViewBox**: Uses the full source image canvas dimensions (`box_w, box_h`, e.g. `1254x1254`).
* **Scale**: Governed by `--scale` (default `0.72`, ~28% padding).
* **Behavior**: Preserves generous, comfortable breathing room inside squircles and framed images. **Do not tightly crop the canvas for padded assets.**

### 2. Unpadded Standalone Assets & Favicons
* **Files**: `logo.svg`, `logo-black.svg`, `logo-white.svg`, `logo-primary.svg`, `logo-gradient.svg`, `logo-currentcolor.svg`, root `logo.svg`, root `favicon.svg`, `favicon.ico`, and transparent `logo-*-{size}.png`.
* **Bounding Box**: Automatically detected via `get_glyph_bbox(input_path)` (`alpha > 80` or luminance threshold).
* **Scale**: Governed by `--unpadded-scale` (default `0.90`).
* **ViewBox**: Square 1:1 `viewBox` centered on the glyph with `box_size = max(gw, gh) / unpadded_scale`.
* **Behavior**: Strips excessive transparent margins from the source raster while adding ~5% balanced breathing room to prevent edge clipping or distortion across standard icon resolutions.

## CLI Options & Usage

```bash
# Basic run
./convert_logo.py logo.png ./output

# Custom palette and scale tuning
./convert_logo.py logo.png ./output \
  --name "My App" \
  --primary "#10b981" \
  --secondary "#34d399" \
  --dark "#059669" \
  --bg-dark "#080c14" \
  --bg-light "#ffffff" \
  --scale 0.72 \
  --unpadded-scale 0.90

# Version and help
./convert_logo.py --version
./convert_logo.py --help
```

## Maintenance & Packaging

- **Single Executable**: Keep `convert_logo.py` self-contained with no mandatory third-party pip dependencies beyond standard libraries (Pillow is auto-detected or falls back to ImageMagick).
- **Version Bumping**: When changing features or CLI flags:
  1. Update `__version__ = "X.Y.Z"` in `convert_logo.py`.
  2. Update `pkgver=X.Y.Z` and reset `pkgrel=1` in `PKGBUILD`.
  3. Verify with `makepkg --printsrcinfo` and `./convert_logo.py --version`.
  4. Update `README.md` if options, outputs, or requirements change.
- **Arch Linux PKGBUILD**:
  - Installs executable to `/usr/bin/convert-logo` with symlink `/usr/bin/convert_logo`.
  - Installs license to `/usr/share/licenses/logo-converter/LICENSE`.
  - Installs documentation to `/usr/share/doc/logo-converter/README.md`.

## Git & Change Workflow

- Core scripts and package definitions live at the repository root.
- **Never run `git commit`** unless the user explicitly asks for a commit in the current message. When asked, write clear, imperative commit messages with concise bulleted descriptions.
- Untracked user scratchpads or temporary directories are not tracked in Git; do not stage or commit them. Never leak local or machine-specific paths into code, documentation, or commits.
- Strictly confine implementation to the specific task requested by the user.
- Maintain this `AGENTS.md` whenever architecture, flags, or packaging conventions evolve.
