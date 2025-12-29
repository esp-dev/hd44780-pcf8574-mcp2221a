from __future__ import annotations

import argparse
import io
from pathlib import Path

from PIL import Image
from PIL import ImageChops, ImageMath, ImageOps
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM


def _render_svg_to_rgb_on_bg(svg_path: Path, size: int, *, bg_rgb: tuple[int, int, int]) -> Image.Image:
    drawing = svg2rlg(str(svg_path))
    if drawing is None:
        raise SystemExit(f"Failed to parse SVG: {svg_path}")

    # svg2rlg preserves original size (1024x1024). Scale to requested size.
    sx = size / float(drawing.width)
    sy = size / float(drawing.height)
    drawing.scale(sx, sy)
    drawing.width = size
    drawing.height = size

    # renderPM renders onto an opaque background. We deliberately control it.
    r, g, b = bg_rgb
    bg_int = (int(r) << 16) | (int(g) << 8) | int(b)
    png_bytes = renderPM.drawToString(drawing, fmt="PNG", bg=bg_int)
    return Image.open(io.BytesIO(png_bytes)).convert("RGB")


def _render_svg_to_rgba(svg_path: Path, size: int) -> Image.Image:
    """Render SVG to RGBA with real transparency.

    ReportLab's renderPM can't reliably emit alpha directly, so we render twice:
    - once on black background (B)
    - once on white background (W)
    For straight alpha compositing per channel:
        B = F * a
        W = F * a + 255 * (1 - a)
    so:
        a = 255 - (W - B)

    This recovers a good alpha mask including anti-aliased edges.
    """

    img_black = _render_svg_to_rgb_on_bg(svg_path, size, bg_rgb=(0, 0, 0))
    img_white = _render_svg_to_rgb_on_bg(svg_path, size, bg_rgb=(255, 255, 255))

    diff = ImageChops.subtract(img_white, img_black)
    alpha = ImageOps.invert(diff.convert("L"))

    # Recover foreground color: F = B / a (scaled to 0..255).
    r_b, g_b, b_b = img_black.split()
    a_f = alpha.convert("F")

    def recover(ch: Image.Image) -> Image.Image:
        ch_f = ch.convert("F")
        out_f = ImageMath.unsafe_eval("p*255.0/(a+1e-6)", p=ch_f, a=a_f)
        return out_f.convert("L")

    r = recover(r_b)
    g = recover(g_b)
    b = recover(b_b)
    return Image.merge("RGBA", (r, g, b, alpha))


def render_svg_to_png(
    svg_path: Path,
    png_path: Path,
    size: int,
    *,
    oversample: int = 1024,
) -> None:
    # Render large, then downscale for crisp small icons.
    base = _render_svg_to_rgba(svg_path, oversample)
    img = base if size == oversample else base.resize((size, size), Image.Resampling.LANCZOS)

    png_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(png_path, format="PNG")


def build_ico(png_paths: list[Path], ico_path: Path) -> None:
    imgs: list[Image.Image] = []
    for p in png_paths:
        imgs.append(Image.open(p).convert("RGBA"))

    if not imgs:
        raise SystemExit("No PNGs provided to build_ico")

    ico_path.parent.mkdir(parents=True, exist_ok=True)

    # Pillow generates icon frames by resizing the *base* image to the requested sizes.
    # If the base is tiny (e.g. 16x16), Pillow cannot magically produce higher-res frames.
    # Use the largest PNG as the base so the .ico contains all sizes.
    base = max(imgs, key=lambda im: im.width * im.height)
    sizes = sorted({(im.width, im.height) for im in imgs})
    base.save(str(ico_path), format="ICO", sizes=sizes)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build PNG/ICO icon assets from assets/icon.svg")
    parser.add_argument("--svg", default="assets/icon.svg", help="Input SVG path")
    parser.add_argument("--out-dir", default="assets", help="Output directory")
    parser.add_argument(
        "--sizes",
        default="16,20,24,32,40,48,64,128,256",
        help="Comma-separated PNG sizes to generate (default: 16,20,24,32,40,48,64,128,256)",
    )
    parser.add_argument(
        "--oversample",
        type=int,
        default=1024,
        help="Render size before downscaling (default: 1024)",
    )
    args = parser.parse_args()

    svg_path = Path(args.svg)
    out_dir = Path(args.out_dir)

    if not svg_path.exists():
        raise SystemExit(f"SVG not found: {svg_path}")

    sizes = [int(s.strip()) for s in str(args.sizes).split(",") if s.strip()]
    sizes = [s for s in sizes if s > 0]
    if not sizes:
        raise SystemExit("No valid sizes provided")

    png_paths: list[Path] = []
    for size in sizes:
        png_path = out_dir / f"icon_{size}.png"
        render_svg_to_png(svg_path, png_path, size, oversample=args.oversample)
        png_paths.append(png_path)

    # Convenience: also write a 1024 preview PNG
    render_svg_to_png(svg_path, out_dir / "icon_1024.png", 1024, oversample=args.oversample)

    ico_path = out_dir / "icon.ico"
    build_ico(png_paths, ico_path)

    print(f"Wrote: {ico_path}")
    for p in png_paths:
        print(f"Wrote: {p}")


if __name__ == "__main__":
    main()
