#!/usr/bin/env python3
"""
Logo Variations Converter CLI
Converts a raster logo (PNG/JPG) into a complete production-ready brand suite:
- Scalable SVGs (Black, White, Primary, Gradient, CurrentColor, Dark/Light BG, Squircle)
- Multi-resolution transparent PNGs (16x16 to 1024x1024)
- Dark & Light themed PNGs and JPGs
- Production favicons (favicon.ico multi-res, favicon.svg, apple-touch-icon.png)
- Web App Manifest (site.webmanifest)

Self-contained & automated:
- Automatically detects and uses system-installed python-pillow (e.g. pacman/apt) even inside a venv.
- Automatically falls back to ImageMagick if Pillow is completely absent.
- Automatically executes all potrace, inkscape, and rsvg-convert conversions.

Usage:
    python convert_logo.py <logo_file_path> <output_dir>
    ./convert_logo.py <logo_file_path> <output_dir>
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

# Auto-detect Pillow (including system pacman/apt packages when inside an isolated venv)
HAS_PIL = False
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    # If running inside a virtualenv, search system site-packages for python-pillow
    for p in glob.glob("/usr/lib/python3*/site-packages") + glob.glob("/usr/lib/python3*/dist-packages"):
        if p not in sys.path:
            sys.path.append(p)
    try:
        from PIL import Image
        HAS_PIL = True
    except ImportError:
        HAS_PIL = False


def check_dependencies():
    """Verify required external binaries are available on PATH."""
    missing = []
    for tool in ["potrace", "rsvg-convert", "inkscape"]:
        if shutil.which(tool) is None:
            missing.append(tool)

    has_magick = shutil.which("magick") or shutil.which("convert")
    if not HAS_PIL and not has_magick:
        missing.append("pillow (or imagemagick)")

    if missing:
        sys.exit(
            f"Error: Missing required system tool(s): {', '.join(missing)}\n\n"
            "Installation commands:\n"
            "  Arch Linux:      sudo pacman -S potrace librsvg inkscape python-pillow\n"
            "  Debian/Ubuntu:   sudo apt install potrace librsvg2-bin inkscape python3-pil\n"
            "  macOS (Homebrew): brew install potrace librsvg inkscape imagemagick"
        )


def make_pbm_mask(image_path: Path, temp_dir: Path) -> Path:
    """
    Generate a 1-bit PBM bitmap mask where 1 = logo shape, 0 = background.
    Works with both transparent PNGs (alpha channel) and solid white/light backgrounds.
    """
    pbm_path = temp_dir / "mask.pbm"

    if HAS_PIL:
        img = Image.open(image_path)
        if "A" in img.getbands():
            alpha = img.split()[-1]
            # In PBM: 1 is black, 0 is white.
            # Pixels with alpha > 80 become black (0 in PIL 1-bit mode, which saves as 1 in PBM)
            bw = alpha.point(lambda p: 0 if p > 80 else 255, mode="1")
        else:
            gray = img.convert("L")
            # Pixels darker than threshold become black (0 in PIL)
            bw = gray.point(lambda p: 0 if p < 200 else 255, mode="1")
        bw.save(str(pbm_path))
    else:
        # Fallback to ImageMagick if Pillow is completely absent
        magick_bin = "magick" if shutil.which("magick") else "convert"
        subprocess.run(
            [magick_bin, str(image_path), "-alpha", "extract", "-threshold", "30%", "-negate", str(pbm_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    return pbm_path


def vectorize_mask(pbm_path: Path, temp_dir: Path) -> Path:
    """Trace the binary PBM mask into smooth vector paths using potrace."""
    raw_svg_path = temp_dir / "traced_raw.svg"
    subprocess.run(
        [
            "potrace",
            str(pbm_path),
            "-s",
            "-o", str(raw_svg_path),
            "-t", "2",
            "-a", "1.1",
            "-n",
            "--opttolerance", "0.2",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return raw_svg_path


def normalize_paths(raw_svg_path: Path, temp_dir: Path) -> tuple[list[str], int, int]:
    """Normalize SVG path coordinates and extract path data strings."""
    plain_svg_path = temp_dir / "plain.svg"
    subprocess.run(
        [
            "inkscape",
            f"--export-filename={plain_svg_path}",
            "--export-plain-svg",
            str(raw_svg_path),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    tree = ET.parse(plain_svg_path)
    root = tree.getroot()

    viewbox = root.attrib.get("viewBox", "")
    if viewbox:
        parts = [float(p) for p in viewbox.split()]
        box_w, box_h = int(parts[2]), int(parts[3])
    else:
        box_w = int(float(root.attrib.get("width", "1254").replace("pt", "").replace("px", "")))
        box_h = int(float(root.attrib.get("height", "1254").replace("pt", "").replace("px", "")))

    path_nodes = root.findall(".//{http://www.w3.org/2000/svg}path") or root.findall(".//path")
    path_data = [p.attrib["d"].strip() for p in path_nodes if "d" in p.attrib]

    if not path_data:
        sys.exit("Error: Failed to extract vector paths from logo.")

    return path_data, box_w, box_h


def build_svg_content(
    path_data: list[str],
    box_w: int,
    box_h: int,
    fill: str = "currentColor",
    bg_color: str | None = None,
    gradient: bool = False,
    rounded: bool = False,
    scale: float = 0.72,
    colors: dict | None = None,
) -> str:
    """Construct clean SVG markup with balanced centering and scaling."""
    colors = colors or {
        "start": "#34d399",
        "mid": "#10b981",
        "end": "#059669",
    }

    defs = ""
    fill_attr = f'fill="{fill}"'
    if gradient:
        defs = f"""  <defs>
    <linearGradient id="brandGradient" x1="10%" y1="10%" x2="90%" y2="90%">
      <stop offset="0%" stop-color="{colors['start']}" />
      <stop offset="50%" stop-color="{colors['mid']}" />
      <stop offset="100%" stop-color="{colors['end']}" />
    </linearGradient>
  </defs>"""
        fill_attr = 'fill="url(#brandGradient)"'

    bg_rect = ""
    if bg_color:
        rx = 'rx="22%" ry="22%"' if rounded else ""
        bg_rect = f'  <rect width="100%" height="100%" fill="{bg_color}" {rx} />\n'

    # Centered scaling transform
    tx = box_w * (1.0 - scale) / 2.0
    ty = box_h - (box_h * (1.0 - scale) / 2.0)
    sx = (scale * 0.1)
    sy = -(scale * 0.1)
    transform_str = f"translate({tx:.2f},{ty:.2f}) scale({sx:.6f},{sy:.6f})"

    path_tags = "\n".join([f'    <path d="{d}" />' for d in path_data])

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {box_w} {box_h}" fill="none">
{defs}
{bg_rect}  <g transform="{transform_str}" {fill_attr} stroke="none">
{path_tags}
  </g>
</svg>"""


def generate_ico(png_16: Path, png_32: Path, png_48: Path, output_ico: Path):
    """Build a multi-resolution favicon.ico containing 16x16, 32x32, and 48x48 layers."""
    if HAS_PIL:
        img16 = Image.open(png_16)
        img32 = Image.open(png_32)
        img48 = Image.open(png_48)
        img48.save(
            str(output_ico),
            format="ICO",
            sizes=[(16, 16), (32, 32), (48, 48)],
            append_images=[img32, img16],
        )
    else:
        magick_bin = "magick" if shutil.which("magick") else "convert"
        subprocess.run(
            [magick_bin, str(png_16), str(png_32), str(png_48), str(output_ico)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )


def convert_png_to_jpg(png_path: Path, jpg_path: Path):
    """Convert PNG to high quality JPEG."""
    if HAS_PIL:
        Image.open(png_path).convert("RGB").save(str(jpg_path), "JPEG", quality=95)
    else:
        magick_bin = "magick" if shutil.which("magick") else "convert"
        subprocess.run(
            [magick_bin, str(png_path), "-quality", "95", str(jpg_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )


class CustomArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that displays the complete help screen on invalid options or errors."""

    def error(self, message):
        sys.stderr.write(f"\n[!] Error: {message}\n\n")
        self.print_help(sys.stderr)
        sys.exit(2)


def main():
    description = """\
Convert a raster logo (PNG, JPG, WebP) into a complete production-ready brand suite:
  - Vector SVGs (Black, White, Primary, Gradient, CurrentColor, Dark/Light BG, Squircle)
  - Multi-resolution transparent PNGs (16x16 up to 1024x1024)
  - Dark & Light themed PNGs and high-quality JPEGs
  - Multi-resolution favicon.ico (16x16, 32x32, 48x48)
  - Adaptive favicon.svg and iOS apple-touch-icon.png
  - Web App Manifest (site.webmanifest)
"""

    epilog = """\
EXAMPLES:
  # Standard conversion:
  convert_logo.py logo.png ./assets

  # Custom brand colors and app title:
  convert_logo.py logo.png ./assets \\
    --name "My App" \\
    --primary "#2563eb" \\
    --secondary "#60a5fa" \\
    --dark "#1d4ed8" \\
    --bg-dark "#0b0f19"

  # Adjust framing scale ratio (default 0.72):
  convert_logo.py logo.png ./assets --scale 0.80

GENERATED ASSET SUITE:
  <output_dir>/
  ├── favicon.ico                   16x16, 32x32, 48x48 multi-resolution icon
  ├── favicon.svg                   Vector favicon crisp on light and dark browser tabs
  ├── apple-touch-icon.png          180x180 squircle app icon for iOS home screen
  ├── android-chrome-192x192.png    192x192 PWA launcher icon
  ├── android-chrome-512x512.png    512x512 high-resolution PWA icon
  ├── favicon-16x16.png             16x16 browser tab PNG
  ├── favicon-32x32.png             32x32 standard browser tab PNG
  ├── favicon-48x48.png             48x48 desktop shortcut PNG
  ├── logo.svg                      Default black vector logo
  ├── site.webmanifest              PWA web manifest
  └── brand/
      ├── logo-black.svg            Solid black vector (#000000)
      ├── logo-white.svg            Solid white vector (#ffffff)
      ├── logo-primary.svg          Primary theme color vector
      ├── logo-gradient.svg         Three-stop linear gradient vector
      ├── logo-currentcolor.svg     Plug-and-play SVG using fill="currentColor"
      ├── logo-dark-bg.svg          Vector on dark background container
      ├── logo-light-bg.svg         Vector on light background container
      ├── logo-squircle-dark.svg    Vector on squircle dark container
      ├── logo-squircle-white.svg   White vector on squircle dark container
      ├── logo-black-{size}.png     Transparent PNGs (16, 32, 48, 64, 128, 256, 512, 1024)
      ├── logo-white-{size}.png     Transparent PNGs (16, 32, 48, 64, 128, 256, 512, 1024)
      ├── logo-primary-{size}.png   Transparent PNGs (16, 32, 48, 64, 128, 256, 512, 1024)
      ├── logo-dark-bg-{size}.png   Dark background PNGs (512, 1024)
      ├── logo-dark-bg-{size}.jpg   Dark background JPGs (512, 1024)
      ├── logo-light-bg-{size}.png  Light background PNGs (512, 1024)
      └── logo-light-bg-{size}.jpg  Light background JPGs (512, 1024)

SYSTEM REQUIREMENTS:
  - potrace        (Bézier vectorizer)
  - rsvg-convert   (librsvg rasterizer)
  - inkscape       (coordinate normalizer)
  - python-pillow  (Pillow library, or ImageMagick as fallback)
"""

    parser = CustomArgumentParser(
        prog="convert_logo.py",
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "logo",
        help="Path to source raster logo file (PNG, JPG, WebP). Transparent PNG recommended.",
    )
    parser.add_argument(
        "output",
        help="Target directory where generated assets and favicons will be saved.",
    )
    parser.add_argument(
        "-p", "--primary",
        default="#10b981",
        metavar="HEX",
        help="Primary brand color (default: #10b981)",
    )
    parser.add_argument(
        "-s", "--secondary",
        default="#34d399",
        metavar="HEX",
        help="Gradient start / highlight color (default: #34d399)",
    )
    parser.add_argument(
        "-d", "--dark",
        default="#059669",
        metavar="HEX",
        help="Gradient end / dark accent color (default: #059669)",
    )
    parser.add_argument(
        "--bg-dark",
        default="#080c14",
        metavar="HEX",
        help="Dark background container color (default: #080c14)",
    )
    parser.add_argument(
        "--bg-light",
        default="#ffffff",
        metavar="HEX",
        help="Light background container color (default: #ffffff)",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=0.72,
        metavar="FLOAT",
        help="Internal framing scale ratio between 0.1 and 1.0 (default: 0.72)",
    )
    parser.add_argument(
        "-n", "--name",
        default="",
        metavar="NAME",
        help="Application / brand name for site.webmanifest (default: derived from filename)",
    )

    # If run with no options/arguments, display full help screen
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    input_path = Path(args.logo).resolve()
    if not input_path.is_file():
        sys.exit(f"\n[!] Error: Input logo file not found: {input_path}\n")

    check_dependencies()

    out_root = Path(args.output).resolve()
    brand_dir = out_root / "brand"
    out_root.mkdir(parents=True, exist_ok=True)
    brand_dir.mkdir(parents=True, exist_ok=True)

    print(f"==> Processing: {input_path.name}")
    print(f"==> Output directory: {out_root}")

    colors = {
        "start": args.secondary,
        "mid": args.primary,
        "end": args.dark,
    }

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)

        # 1. Extract Mask & Vectorize
        print(" -> Extracting foreground mask and vectorizing with potrace...")
        pbm_path = make_pbm_mask(input_path, temp_dir)
        raw_svg = vectorize_mask(pbm_path, temp_dir)
        path_data, box_w, box_h = normalize_paths(raw_svg, temp_dir)
        print(f" -> Extracted {len(path_data)} smooth vector path(s) ({box_w}x{box_h})")

        # 2. Build SVG Variants
        print(" -> Generating SVG variants...")
        svg_variants = {
            # Brand folder
            brand_dir / "logo.svg": build_svg_content(path_data, box_w, box_h, fill="#000000", scale=args.scale),
            brand_dir / "logo-black.svg": build_svg_content(path_data, box_w, box_h, fill="#000000", scale=args.scale),
            brand_dir / "logo-white.svg": build_svg_content(path_data, box_w, box_h, fill="#ffffff", scale=args.scale),
            brand_dir / "logo-primary.svg": build_svg_content(path_data, box_w, box_h, fill=args.primary, scale=args.scale),
            brand_dir / "logo-gradient.svg": build_svg_content(path_data, box_w, box_h, gradient=True, scale=args.scale, colors=colors),
            brand_dir / "logo-currentcolor.svg": build_svg_content(path_data, box_w, box_h, fill="currentColor", scale=args.scale),
            brand_dir / "logo-dark-bg.svg": build_svg_content(path_data, box_w, box_h, gradient=True, bg_color=args.bg_dark, scale=args.scale, colors=colors),
            brand_dir / "logo-dark-bg-white.svg": build_svg_content(path_data, box_w, box_h, fill="#ffffff", bg_color=args.bg_dark, scale=args.scale),
            brand_dir / "logo-light-bg.svg": build_svg_content(path_data, box_w, box_h, gradient=True, bg_color=args.bg_light, scale=args.scale, colors=colors),
            brand_dir / "logo-squircle-dark.svg": build_svg_content(path_data, box_w, box_h, gradient=True, bg_color=args.bg_dark, rounded=True, scale=args.scale, colors=colors),
            brand_dir / "logo-squircle-white.svg": build_svg_content(path_data, box_w, box_h, fill="#ffffff", bg_color=args.bg_dark, rounded=True, scale=args.scale),
            # Root public files
            out_root / "logo.svg": build_svg_content(path_data, box_w, box_h, fill="#000000", scale=args.scale),
            out_root / "favicon.svg": build_svg_content(path_data, box_w, box_h, gradient=True, scale=args.scale, colors=colors),
        }

        for path, svg_code in svg_variants.items():
            path.write_text(svg_code, encoding="utf-8")

        # 3. Generate PNGs across all standard sizes
        print(" -> Generating multi-resolution PNGs...")
        sizes = [16, 32, 48, 64, 128, 256, 512, 1024]
        for name, src_svg in [
            ("black", brand_dir / "logo-black.svg"),
            ("white", brand_dir / "logo-white.svg"),
            ("primary", brand_dir / "logo-gradient.svg"),
        ]:
            for sz in sizes:
                subprocess.run(
                    ["rsvg-convert", "-w", str(sz), "-h", str(sz), str(src_svg), "-o", str(brand_dir / f"logo-{name}-{sz}x{sz}.png")],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

        # 4. Background PNGs and JPGs
        print(" -> Generating framed background PNGs and JPGs...")
        for sz in [512, 1024]:
            dark_png = brand_dir / f"logo-dark-bg-{sz}x{sz}.png"
            light_png = brand_dir / f"logo-light-bg-{sz}x{sz}.png"
            squircle_png = brand_dir / f"logo-squircle-dark-{sz}x{sz}.png"

            subprocess.run(
                ["rsvg-convert", "-w", str(sz), "-h", str(sz), str(brand_dir / "logo-dark-bg.svg"), "-o", str(dark_png)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                ["rsvg-convert", "-w", str(sz), "-h", str(sz), str(brand_dir / "logo-light-bg.svg"), "-o", str(light_png)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                ["rsvg-convert", "-w", str(sz), "-h", str(sz), str(brand_dir / "logo-squircle-dark.svg"), "-o", str(squircle_png)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            convert_png_to_jpg(dark_png, brand_dir / f"logo-dark-bg-{sz}x{sz}.jpg")
            convert_png_to_jpg(light_png, brand_dir / f"logo-light-bg-{sz}x{sz}.jpg")

        # 5. Root Favicons & App Icons
        print(" -> Generating favicon suite & web manifest...")
        subprocess.run(
            ["rsvg-convert", "-w", "180", "-h", "180", str(brand_dir / "logo-squircle-dark.svg"), "-o", str(out_root / "apple-touch-icon.png")],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            ["rsvg-convert", "-w", "192", "-h", "192", str(brand_dir / "logo-squircle-dark.svg"), "-o", str(out_root / "android-chrome-192x192.png")],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            ["rsvg-convert", "-w", "512", "-h", "512", str(brand_dir / "logo-squircle-dark.svg"), "-o", str(out_root / "android-chrome-512x512.png")],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        for sz in [16, 32, 48]:
            subprocess.run(
                ["rsvg-convert", "-w", str(sz), "-h", str(sz), str(out_root / "favicon.svg"), "-o", str(out_root / f"favicon-{sz}x{sz}.png")],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        generate_ico(
            out_root / "favicon-16x16.png",
            out_root / "favicon-32x32.png",
            out_root / "favicon-48x48.png",
            out_root / "favicon.ico",
        )

        # 6. Web Manifest
        app_name = args.name.strip() if args.name else input_path.stem.replace("_", " ").replace("-", " ").title()
        manifest = f"""{{
  "name": "{app_name}",
  "short_name": "{app_name.split()[0] if app_name else 'App'}",
  "icons": [
    {{
      "src": "/android-chrome-192x192.png",
      "sizes": "192x192",
      "type": "image/png"
    }},
    {{
      "src": "/android-chrome-512x512.png",
      "sizes": "512x512",
      "type": "image/png"
    }}
  ],
  "theme_color": "{args.primary}",
  "background_color": "{args.bg_dark}",
  "display": "standalone",
  "start_url": "/"
}}
"""
        (out_root / "site.webmanifest").write_text(manifest, encoding="utf-8")

    print(f"\n[Done] Successfully generated complete logo & favicon suite in: {out_root}")


if __name__ == "__main__":
    main()
