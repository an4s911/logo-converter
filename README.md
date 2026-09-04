# Logo Converter

A standalone CLI tool to convert any raster logo (PNG, JPG, WebP) into a complete, production-ready brand suite: scalable vector SVGs, multi-resolution transparent PNGs, framed dark/light assets, multi-resolution favicons, and PWA manifests.

---

## 1. Quick Start (CLI Usage)

The CLI tool is `convert_logo.py`.

### Basic Usage

```bash
# Direct execution (executable):
./convert_logo.py <logo_file_path> <output_dir>

# Or running with python:
python convert_logo.py <logo_file_path> <output_dir>
```

### Help Screen & Options (`-h` / `--help`)

The script features a standard POSIX/GNU help screen.
Running `convert_logo.py` with **`-h`**, **`--help`**, **no arguments**, or **invalid arguments** displays this help message:

```bash
./convert_logo.py -h
```

| Flag | Short | Default | Description |
| :--- | :---: | :---: | :--- |
| `logo` | — | *(required)* | Path to source raster logo (PNG, JPG, WebP). Transparent PNG recommended. |
| `output` | — | *(required)* | Target directory where the asset bundle and favicons will be saved. |
| `--help` | `-h` | — | Show help message and exit. |
| `--primary` | `-p` | `#10b981` | Primary brand HEX color. |
| `--secondary` | `-s` | `#34d399` | Gradient start / highlight HEX color. |
| `--dark` | `-d` | `#059669` | Gradient end / dark accent HEX color. |
| `--bg-dark` | — | `#080c14` | Dark container and webmanifest background HEX color. |
| `--bg-light` | — | `#ffffff` | Light container background HEX color. |
| `--scale` | — | `0.72` | Internal framing scale ratio between 0.1 and 1.0 (breathing room). |
| `--name` | `-n` | *(filename)* | Application / brand display name in `site.webmanifest`. |

### Installation

#### Arch Linux (PKGBUILD)

Build and install using `makepkg` (automatically resolves dependencies via pacman and registers `convert-logo` system-wide):

```bash
makepkg -si
```

#### Manual Installation (Any Linux / macOS)

```bash
chmod +x convert_logo.py
# User-level install:
cp convert_logo.py ~/.local/bin/convert-logo

# Or system-wide install:
sudo cp convert_logo.py /usr/local/bin/convert-logo
```

### Custom Brand Colors & App Name (Optional)

You can customize the color palette and app title via CLI flags:

```bash
./convert_logo.py logo.png ./output \
  --name "My App" \
  --primary "#10b981" \
  --secondary "#34d399" \
  --dark "#059669" \
  --bg-dark "#080c14" \
  --bg-light "#ffffff"
```

### Generated Output Structure

Running the script produces the following complete asset bundle:

```
<output_dir>/
├── favicon.ico                   # Multi-resolution ICO (16x16, 32x32, 48x48)
├── favicon.svg                   # Scalable vector favicon (crisp on dark & light tabs)
├── apple-touch-icon.png          # 180x180 iOS squircle home screen icon
├── android-chrome-192x192.png    # 192x192 Android PWA icon
├── android-chrome-512x512.png    # 512x512 High-res Android PWA icon
├── favicon-16x16.png             # 16x16 browser favicon PNG
├── favicon-32x32.png             # 32x32 standard browser favicon PNG
├── favicon-48x48.png             # 48x48 desktop shortcut PNG
├── logo.svg                      # Default plug-and-play black SVG
├── site.webmanifest              # PWA manifest pointing to chrome icons
└── brand/
    ├── logo.svg                  # Default black SVG
    ├── logo-black.svg            # Pure black (#000000)
    ├── logo-white.svg            # Pure white (#ffffff)
    ├── logo-primary.svg          # Primary theme color
    ├── logo-gradient.svg         # Primary gradient
    ├── logo-currentcolor.svg     # Uses fill="currentColor" for Tailwind / CSS inheritance
    ├── logo-dark-bg.svg          # Framed on dark background
    ├── logo-light-bg.svg         # Framed on light background
    ├── logo-squircle-dark.svg    # Framed on rounded squircle container
    ├── logo-squircle-white.svg   # Framed white logo on dark squircle
    ├── logo-black-{size}.png     # Transparent PNGs: 16, 32, 48, 64, 128, 256, 512, 1024
    ├── logo-white-{size}.png     # Transparent PNGs: 16, 32, 48, 64, 128, 256, 512, 1024
    ├── logo-primary-{size}.png   # Transparent PNGs: 16, 32, 48, 64, 128, 256, 512, 1024
    ├── logo-dark-bg-{size}.png   # Dark background PNGs (512, 1024)
    ├── logo-dark-bg-{size}.jpg   # Dark background JPGs (512, 1024)
    ├── logo-light-bg-{size}.png  # Light background PNGs (512, 1024)
    └── logo-light-bg-{size}.jpg  # Light background JPGs (512, 1024)
```

---

## 2. Technical Pipeline & Code Implementation

Here is the exact step-by-step process used to convert the raster logo into vectors and multi-format variants.

### Step 1: Binary Mask Extraction (Zero NumPy)

To convert an image to vector paths, we extract a 1-bit binary mask (PBM format) where `1` represents the logo mark and `0` represents the background.

```python
from PIL import Image

def make_pbm_mask(image_path: Path, output_pbm: Path):
    img = Image.open(image_path)
    
    # If the image has an alpha channel, use alpha thresholding:
    if "A" in img.getbands():
        alpha = img.split()[-1]
        # Pixels with alpha > 80 become black (0 in PIL 1-bit, which writes as 1 in PBM)
        bw = alpha.point(lambda p: 0 if p > 80 else 255, mode="1")
    else:
        # For solid light backgrounds, use luminance thresholding:
        gray = img.convert("L")
        bw = gray.point(lambda p: 0 if p < 200 else 255, mode="1")
        
    bw.save(str(output_pbm))
```

> **Why PBM?** `potrace` requires a 1-bit monochrome bitmap (`.pbm` format) to extract vector outlines. Pillow can write PBM natively without needing NumPy.

---

### Step 2: Bézier Vectorization with Potrace

`potrace` transforms the high-resolution pixel bitmap into smooth Bézier vector splines:

```python
import subprocess

subprocess.run([
    "potrace",
    "mask.pbm",
    "-s",                   # Output SVG
    "-o", "traced_raw.svg",
    "-t", "2",              # Suppress speckles/noise smaller than 2px
    "-a", "1.1",            # Corner threshold for smooth curves
    "-n",                   # Don't group paths
    "--opttolerance", "0.2" # High precision curve fitting
], check=True)
```

---

### Step 3: SVG Coordinate Normalization & Centered Framing

Potrace outputs coordinates with a Y-inverted transform (`scale(0.1, -0.1)`). We normalize it and apply a centered scale transformation (`scale=0.72`) so the logo has balanced breathing room when placed inside containers, favicons, and app icons:

```python
import xml.etree.ElementTree as ET
import subprocess

# Flatten and export plain SVG using Inkscape
subprocess.run([
    "inkscape",
    "--export-filename=plain.svg",
    "--export-plain-svg",
    "traced_raw.svg"
], check=True)

# Parse path data
tree = ET.parse("plain.svg")
root = tree.getroot()
path_nodes = root.findall(".//{http://www.w3.org/2000/svg}path") or root.findall(".//path")
path_data = [p.attrib["d"].strip() for p in path_nodes if "d" in p.attrib]

# Apply centered framing (scale = 0.72) inside a 1254x1254 coordinate box
box_w, box_h = 1254, 1254
scale = 0.72

tx = box_w * (1.0 - scale) / 2.0
ty = box_h - (box_h * (1.0 - scale) / 2.0)
sx = scale * 0.1
sy = -(scale * 0.1)
transform_str = f"translate({tx:.2f},{ty:.2f}) scale({sx:.6f},{sy:.6f})"
```

---

### Step 4: Generating Plug-and-Play SVG Variations

We assemble clean SVG markup with customizable fills:

* **Plug-and-Play (`fill="currentColor"`)**: Inherits color directly from CSS or Tailwind classes (`text-emerald-500`, `text-white`, `hover:text-emerald-300`).
* **Gradient**: Embedded `<linearGradient>` with smooth transitions.
* **Squircle Badge**: Adds `<rect width="100%" height="100%" fill="{bg_dark}" rx="22%" ry="22%" />` behind the paths.

```python
def build_svg(fill="currentColor", bg_color=None, gradient=False, rounded=False):
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

    path_tags = "\n".join([f'    <path d="{d}" />' for d in path_data])

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {box_w} {box_h}" fill="none">
{defs}
{bg_rect}  <g transform="{transform_str}" {fill_attr} stroke="none">
{path_tags}
  </g>
</svg>"""
```

---

### Step 5: Multi-Resolution Rasterization with `rsvg-convert`

`rsvg-convert` renders vector SVGs into pixel-perfect PNGs at any target resolution with high-fidelity anti-aliasing:

```bash
# Syntax: rsvg-convert -w <width> -h <height> <input.svg> -o <output.png>
rsvg-convert -w 512 -h 512 logo-gradient.svg -o logo-primary-512x512.png
rsvg-convert -w 180 -h 180 logo-squircle-dark.svg -o apple-touch-icon.png
rsvg-convert -w 32 -h 32 favicon.svg -o favicon-32x32.png
```

---

### Step 6: Multi-Resolution Favicon Packaging (`favicon.ico`)

A standards-compliant `favicon.ico` contains multiple icon resolutions (16x16, 32x32, 48x48) embedded in a single binary file so older desktop browsers and OS shortcuts pick the sharpest version:

```python
from PIL import Image

img16 = Image.open("favicon-16x16.png")
img32 = Image.open("favicon-32x32.png")
img48 = Image.open("favicon-48x48.png")

img48.save(
    "favicon.ico",
    format="ICO",
    sizes=[(16, 16), (32, 32), (48, 48)],
    append_images=[img32, img16],
)
```

---

## 3. Ideal Logo Characteristics

The converter pipeline is optimized for:

* **Monochrome & Silhouette Marks**: Logos where the identity is conveyed through shape, geometry, or solid forms (such as Apple, Nike, Twitter/X, lettermarks, or stylized glyphs).
* **Single or Dual Tone Shapes**: Logos designed to look iconic in black, white, or a solid brand color.
* **Transparent PNGs (RGBA)**: Clean alpha channel masks produce the cleanest vector curves.
* **High Resolution (1024x1024 or higher)**: Higher source resolution provides Potrace with more subpixel data, producing smoother Bézier curves without pixelation bumps.

---

## 4. Constraints & Limitations

The vectorizer uses 1-bit thresholding (`potrace`). Keep these constraints in mind:

| Logo Type / Feature | Works? | Explanation & Behavior |
| :--- | :---: | :--- |
| **Monochrome Glyph / Lettermark** | ✅ **Ideal** | Extracts clean Bézier curves; recolors easily. |
| **High-Res Transparent PNG** | ✅ **Ideal** | Alpha mask detects exact silhouette boundaries. |
| **Solid White BG with Dark Logo** | ✅ **Good** | Luminance thresholding cleanly extracts foreground. |
| **Multi-Colored Logos (3+ distinct colors)** | ⚠️ **Limited** | The tracer collapses all colored shapes into a single unified 1-bit silhouette. It will not retain separate colors per path unless manually split. |
| **Photographic or Realistic Images** | ❌ **No** | Photos produce thousands of noisy, jagged vector polygons. |
| **Embedded Gradients in Source PNG** | ⚠️ **Limited** | The threshold will clip the gradient into a hard boundary. (Note: The script reapplies clean SVG gradients to the resulting shape). |
| **Thin Lines in Low-Res Images (< 200px)** | ❌ **No** | Pixelation causes Potrace to create bumpy or broken paths. Always supply high-res sources. |

---

## 5. System Requirements

The script requires standard Linux/macOS graphics utilities:

```bash
# Arch Linux / Manjaro
sudo pacman -S potrace librsvg inkscape imagemagick python-pillow

# Debian / Ubuntu / Linux Mint
sudo apt update && sudo apt install -y potrace librsvg2-bin inkscape imagemagick python3-pil

# macOS (Homebrew)
brew install potrace librsvg inkscape imagemagick
```
