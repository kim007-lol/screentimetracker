"""Build Drako's static pill and roaming assets from the delivered stage art.

Momo's assets are never read or written here. The stage portraits live in
docs/docs-assets-chr/paket-drako-3d-final; this script only produces new
`*_drako_*` resources in drawable-xxxhdpi.

Pipeline mirrors make_pill_sprites.py: cut the plain white studio background
from the border, trim to alpha, then fit a padded canvas without touching an
edge. Tired and critical faces are derived from the fresh portrait in place
(no ImageGen quota available), keeping the same head, horns and lighting.

Usage:
  python tools/make_drako_sprites.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_pill_sprites import (  # noqa: E402
    BODY_PAD,
    TARGET,
    clean_body,
    edge_report,
    fit_portrait,
    fit_square,
    remove_background,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "docs-assets-chr" / "paket-drako-3d-final"
OUT = ROOT / "mobile" / "android" / "app" / "src" / "main" / "res" / "drawable-xxxhdpi"
PREVIEW = ROOT / "tools" / "drako_sprite_preview.png"

HEAD_CROP = {
    "bayi": (170, 80, 1080, 1082),
    "remaja": (450, 20, 1100, 565),
    "dewasa": (700, 30, 1225, 560),
}
# Below this local y only the central chin/neck survives. The stage art has
# wing and chest fragments at the bottom edge that would read as a red beard
# in a floating pill head.
LOWER_MASK = {
    "bayi": (990, 200, 700),
    "remaja": (520, 100, 550),
    "dewasa": (440, 55, 430),
}
HEAD_PAD = 14

# Eye centres in source coordinates, with the approximate eye radius. Used to
# place the mood drops relative to the face.
EYES = {
    "bayi": [((450, 785), (105, 108)), ((820, 785), (105, 108))],
    "remaja": [((607, 350), (56, 62)), ((855, 350), (56, 62))],
    "dewasa": [((882, 347), (45, 24)), ((1064, 347), (45, 24))],
}

# Adult wings are wider than the portrait body canvas; a landscape canvas keeps
# the full-body pill form from looking tiny inside the 64dp holder.
BODY_SIZE = {
    "bayi": (224, 288),
    "remaja": (224, 288),
    "dewasa": (288, 224),
}

ROAM = 512
ROAM_PAD = 6


def head_source(stage: str) -> Image.Image:
    im = Image.open(SRC / f"drako_{stage}.png").convert("RGB")
    return im.crop(HEAD_CROP[stage])


def drop(face: Image.Image, x: int, y: int, w: int, h: int) -> None:
    """A soft teal drop, used for sweat and tears."""
    shape = Image.new("RGBA", (20, 28), (0, 0, 0, 0))
    d = ImageDraw.Draw(shape)
    d.ellipse((4, 8, 16, 25), fill=(178, 232, 255, 225))
    d.polygon(((10, 0), (17, 13), (3, 13)), fill=(178, 232, 255, 225))
    d.ellipse((7, 13, 11, 19), fill=(255, 255, 255, 235))
    shape = shape.resize((max(3, w), max(4, h)), Image.LANCZOS)
    face.paste(shape, (x, y), shape)


def fitted_eyes(cut: Image.Image, stage: str) -> list[tuple[int, int]]:
    """Map source eye centres into the 192px fitted canvas."""
    bbox = cut.getbbox()
    assert bbox is not None
    trim = cut.crop(bbox)
    inner = TARGET - HEAD_PAD * 2
    scale = min(inner / trim.width, inner / trim.height)
    ox = (TARGET - round(trim.width * scale)) // 2
    oy = (TARGET - round(trim.height * scale)) // 2
    crop_x, crop_y = HEAD_CROP[stage][:2]
    points = []
    for eye, _ in EYES[stage]:
        ex = ox + (eye[0] - crop_x - bbox[0]) * scale
        ey = oy + (eye[1] - crop_y - bbox[1]) * scale
        points.append((int(ex), int(ey)))
    return points


def build_head(stage: str, mood: str) -> Image.Image:
    im = head_source(stage)
    cut = remove_background(im)
    mask = LOWER_MASK.get(stage)
    if mask:
        cut_y, keep_x0, keep_x1 = mask
        alpha = cut.getchannel("A")
        px = alpha.load()
        for y in range(cut_y, cut.height):
            for x in range(cut.width):
                if x < keep_x0 or x > keep_x1:
                    px[x, y] = 0
        cut.putalpha(alpha)
    sprite = fit_square(cut, TARGET, HEAD_PAD)
    if mood == "fresh":
        return sprite

    # The delivered art has painted eyes, not a facial rig, and the image
    # generator is unavailable. Mood is carried honestly by a grade plus a
    # sweat/tear drop instead of faking a redrawn eyelid.
    color = 0.72 if mood == "tired" else 0.62
    brightness = 0.95 if mood == "tired" else 0.90
    face = ImageEnhance.Color(sprite.convert("RGB")).enhance(color)
    face = ImageEnhance.Brightness(face).enhance(brightness)
    rgba = face.convert("RGBA")
    rgba.putalpha(sprite.getchannel("A"))

    (left_x, left_y), (right_x, right_y) = fitted_eyes(cut, stage)
    scale = {"bayi": 1.0, "remaja": 0.9, "dewasa": 0.75}[stage]
    if mood == "tired":
        drop(rgba, right_x + 22, right_y - 34,
             int(6 * scale + 3), int(9 * scale + 4))
    else:
        drop(rgba, right_x + 2, right_y + 10, int(6 * scale + 2),
             int(9 * scale + 3))
        drop(rgba, left_x - 6, left_y + 11, int(5 * scale + 2),
             int(8 * scale + 3))
    return rgba


def clean_floor(sprite: Image.Image) -> Image.Image:
    """Drop neutral floor shadow left under the feet.

    clean_body removes the shadow that reaches the crop border. The delivered
    art also has a soft gray wash between the feet; per column, anything neutral
    below that column's lowest coloured pixel is floor, not fur.
    """
    px = sprite.load()
    w, h = sprite.size
    for x in range(w):
        bottom = -1
        for y in range(h):
            r, g, b, a = px[x, y]
            if a > 0 and max(r, g, b) - min(r, g, b) > 28:
                bottom = y
        for y in range(bottom + 1, h):
            r, g, b, a = px[x, y]
            if a > 0:
                px[x, y] = (0, 0, 0, 0)
    return sprite


def build_body(stage: str) -> Image.Image:
    im = Image.open(SRC / f"drako_{stage}.png").convert("RGB")
    sprite = remove_background(im)
    bbox = sprite.getbbox()
    if bbox:
        sprite = sprite.crop(bbox)
    sprite = clean_body(sprite)
    sprite = clean_floor(sprite)
    return fit_portrait(sprite, BODY_SIZE[stage], BODY_PAD)


def _shadow(size: int) -> Image.Image:
    """Soft floor shadow for the roaming poster."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    w = int(size * 0.42)
    h = int(size * 0.075)
    left = (size - w) // 2
    # Keep the blurred shadow inside the canvas; a hard alpha cut on the
    # bottom edge would draw a visible line over other apps.
    top = size - h - 34
    ImageDraw.Draw(mask).ellipse((left, top, left + w, top + h), fill=70)
    mask = mask.filter(ImageFilter.GaussianBlur(size * 0.012))
    layer.putalpha(mask)
    return layer


def build_roam(stage: str) -> Image.Image:
    # Re-open the cleaned body at full poster scale instead of enlarging the
    # 224x288 pill body, so the overlay stays sharp.
    im = Image.open(SRC / f"drako_{stage}.png").convert("RGB")
    sprite = remove_background(im)
    bbox = sprite.getbbox()
    if bbox:
        sprite = sprite.crop(bbox)
    sprite = clean_body(sprite)
    sprite = clean_floor(sprite)
    scale = min((ROAM - ROAM_PAD * 2) / sprite.width,
                (ROAM - ROAM_PAD * 2) / sprite.height)
    sprite = sprite.resize(
        (max(1, round(sprite.width * scale)), max(1, round(sprite.height * scale))),
        Image.LANCZOS,
    )
    canvas = Image.new("RGBA", (ROAM, ROAM), (0, 0, 0, 0))
    x = (ROAM - sprite.width) // 2
    y = ROAM - ROAM_PAD - sprite.height
    canvas.alpha_composite(_shadow(ROAM), (0, 0))
    canvas.alpha_composite(sprite, (x, y))
    return canvas


def grid(tiles: list[tuple[str, Image.Image]], out: Path, cell: int, pad: int = 10) -> None:
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (cell + pad) + pad, rows * (cell + pad) + pad), (24, 24, 27))
    for i, (_, tile) in enumerate(tiles):
        col, row = i % cols, i // cols
        sheet.paste(tile, (pad + col * (cell + pad), pad + row * (cell + pad)), tile)
    sheet.save(out)
    print(f"preview -> {out}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    heads = []
    for stage in ("bayi", "remaja", "dewasa"):
        for mood in ("fresh", "tired", "critical"):
            sprite = build_head(stage, mood)
            name = f"pill_mascot_drako_{stage}" + ("" if mood == "fresh" else f"_{mood}")
            dest = OUT / f"{name}.png"
            sprite.save(dest)
            print(f"{dest.name:42s} edge alpha {edge_report(sprite)}")
            heads.append((name, sprite))
    grid(heads, PREVIEW, TARGET)

    bodies = []
    for stage in ("bayi", "remaja", "dewasa"):
        sprite = build_body(stage)
        dest = OUT / f"pill_body_drako_{stage}.png"
        sprite.save(dest)
        print(f"{dest.name:42s} edge alpha {edge_report(sprite)}")
        bodies.append((dest.name, sprite))
    grid(bodies, ROOT / "tools" / "drako_body_preview.png", 288)

    roams = []
    for stage in ("bayi", "remaja", "dewasa"):
        sprite = build_roam(stage)
        dest = OUT / f"pet_roam_drako_{stage}.png"
        sprite.save(dest)
        print(f"{dest.name:42s} edge alpha {edge_report(sprite)}")
        roams.append((dest.name, sprite))
    grid(roams, ROOT / "tools" / "drako_roam_preview.png", ROAM)
    return 0


if __name__ == "__main__":
    sys.exit(main())
