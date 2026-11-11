"""Build centered 192x192 RGBA pill sprites from a render with a plain background.

Pipeline: crop the head region, flood-fill the background from the border to
transparency, trim to the alpha bounding box, scale to fit a padded square and
center it. Outputs never touch the border, so the mascot can never be clipped.
"""
from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "mobile" / "android" / "app" / "src" / "main" / "res" / "drawable-xxxhdpi"
PREVIEW = ROOT / "tools" / "pill_sprite_preview.png"

CROPS = {
    "bayi": (0, 330, 800, 1040),
    "remaja": (80, 40, 820, 890),
    "dewasa": (180, 30, 900, 1010),
}

# Generated expression art (already framed with free margins on all sides).
EXPRESSIONS = {
    ("bayi", "tired"): "vibe_images/pill_mascot_bayi_tired_1793248160495_7ac3c72b.png",
    ("bayi", "critical"): "vibe_images/pill_mascot_bayi_critical_1793248226340_19b785cd.png",
    ("remaja", "tired"): "vibe_images/pill_mascot_remaja_tired_1793248253755_26c94e49.png",
    ("remaja", "critical"): "vibe_images/pill_mascot_remaja_critical_1793248296604_0fbe78eb.png",
    ("dewasa", "tired"): "vibe_images/pill_mascot_dewasa_tired_1793248337924_d363ca66.png",
    ("dewasa", "critical"): "vibe_images/pill_mascot_dewasa_critical_1793248376285_60c767aa.png",
}

TARGET = 192
PAD = 16
# The pill's full-body form. 4x for a 64 dp holder at xxxhdpi.
BODY_TARGET = (224, 288)
BODY_PAD = 8

# Areas erased before trimming, in source coordinates (used to drop the tail
# that peeks into a head crop).
ERASE = {
    "bayi": [(762, 1000, 1120, 2240)],
}


def remove_background(im: Image.Image, tolerance: int = 18) -> Image.Image:
    rgb = im.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    mask = Image.new("L", (w, h), 0)
    mpx = mask.load()
    visited = bytearray(w * h)
    queue: deque[tuple[int, int]] = deque()

    def near_white(x: int, y: int) -> bool:
        r, g, b = px[x, y]
        return min(r, g, b) >= 255 - tolerance and max(r, g, b) - min(r, g, b) <= tolerance

    for x in range(w):
        for y in (0, h - 1):
            if near_white(x, y) and not visited[y * w + x]:
                visited[y * w + x] = 1
                queue.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if near_white(x, y) and not visited[y * w + x]:
                visited[y * w + x] = 1
                queue.append((x, y))

    while queue:
        x, y = queue.popleft()
        mpx[x, y] = 1
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not visited[ny * w + nx] and near_white(nx, ny):
                visited[ny * w + nx] = 1
                queue.append((nx, ny))

    alpha = mask.point(lambda v: 0 if v else 255)
    # Soften the hard cut so scaled-down edges do not look jagged.
    alpha = alpha.filter(ImageFilter.GaussianBlur(1.0))
    rgba = rgb.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba


def fit_square(im: Image.Image, size: int = TARGET, pad: int = PAD) -> Image.Image:
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    inner = size - pad * 2
    scale = min(inner / im.width, inner / im.height)
    new = (max(1, round(im.width * scale)), max(1, round(im.height * scale)))
    im = im.resize(new, Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(im, ((size - im.width) // 2, (size - im.height) // 2))
    return canvas


def fit_portrait(im: Image.Image, size: tuple[int, int], pad: int) -> Image.Image:
    """Fit a tall sprite into a portrait canvas without touching any edge."""
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    width, height = size
    scale = min((width - pad * 2) / im.width, (height - pad * 2) / im.height)
    new = (max(1, round(im.width * scale)), max(1, round(im.height * scale)))
    im = im.resize(new, Image.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.alpha_composite(im, ((width - im.width) // 2, height - pad - im.height))
    return canvas


def edge_report(im: Image.Image) -> str:
    a = im.getchannel("A")
    w, h = a.size
    edges = {
        "L": max(a.getpixel((0, y)) for y in range(h)),
        "T": max(a.getpixel((x, 0)) for x in range(w)),
        "R": max(a.getpixel((w - 1, y)) for y in range(h)),
        "B": max(a.getpixel((x, h - 1)) for x in range(w)),
    }
    return " ".join(f"{k}{v}" for k, v in edges.items())


def build(stage: str, src: Path, dest: Path, crop: tuple[int, int, int, int] | None) -> None:
    im = Image.open(src).convert("RGB")
    if crop:
        im = im.crop(crop)
    sprite = remove_background(im)
    if crop:
        for x0, y0, x1, y1 in ERASE.get(stage, []):
            box = (max(0, x0 - crop[0]), max(0, y0 - crop[1]),
                   min(sprite.width, x1 - crop[0]), min(sprite.height, y1 - crop[1]))
            if box[2] > box[0] and box[3] > box[1]:
                sprite.paste((0, 0, 0, 0), box)
    sprite = fit_square(sprite)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sprite.save(dest)
    print(f"{dest.name:34s} edge alpha {edge_report(sprite)}")


def clean_body(sprite: Image.Image) -> Image.Image:
    """Erase leftover background the border flood fill cannot reach.

    The portraits enclose white behind the legs and tail: a pure-white gap that
    connects to a floor strip, and a light shadow. At 64 dp both become pale
    smudges. Opaque pure-white islands are removed whole; anything light and
    near-neutral below the lowest saturated fur is cleared as floor shadow.
    """
    px = sprite.load()
    w, h = sprite.size

    def pure_white(x: int, y: int) -> bool:
        r, g, b, a = px[x, y]
        return a > 0 and min(r, g, b) >= 248 and max(r, g, b) - min(r, g, b) <= 6

    visited = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            index = y * w + x
            if visited[index] or not pure_white(x, y):
                continue
            visited[index] = 1
            stack = [(x, y)]
            points: list[tuple[int, int]] = []
            while stack:
                cx, cy = stack.pop()
                points.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy),
                               (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        n = ny * w + nx
                        if not visited[n] and pure_white(nx, ny):
                            visited[n] = 1
                            stack.append((nx, ny))
            if len(points) >= 400:
                for cx, cy in points:
                    px[cx, cy] = (0, 0, 0, 0)

    fur_bottom = -1
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 0 and max(r, g, b) - min(r, g, b) >= 30:
                fur_bottom = y
                break
    if fur_bottom >= 0:
        for y in range(fur_bottom + 1, h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a > 0 and min(r, g, b) >= 210 and max(r, g, b) - min(r, g, b) <= 24:
                    px[x, y] = (0, 0, 0, 0)

    # The portrait's floor shadow is a pale neutral wash that spans past the
    # body and touches the crop's left/right border; fur markings never do.
    # Seeding only from the sides keeps a white belly or paw pads that reach
    # the bottom edge intact. The band stops the flood from climbing a pale
    # leg into the chest ruff.
    floor_top = int(h * 0.72)

    def floor_like(x: int, y: int) -> bool:
        if y < floor_top:
            return False
        r, g, b, a = px[x, y]
        return a > 0 and min(r, g, b) >= 170 and max(r, g, b) - min(r, g, b) <= 30

    seen = bytearray(w * h)
    queue: deque[tuple[int, int]] = deque()
    for y in range(floor_top, h):
        for x in (0, w - 1):
            if floor_like(x, y) and not seen[y * w + x]:
                seen[y * w + x] = 1
                queue.append((x, y))
    floor: list[tuple[int, int]] = []
    while queue:
        cx, cy = queue.popleft()
        floor.append((cx, cy))
        for nx, ny in ((cx + 1, cy), (cx - 1, cy),
                       (cx, cy + 1), (cx, cy - 1)):
            if 0 <= nx < w and 0 <= ny < h:
                n = ny * w + nx
                if not seen[n] and floor_like(nx, ny):
                    seen[n] = 1
                    queue.append((nx, ny))
    if len(floor) >= 120:
        for cx, cy in floor:
            px[cx, cy] = (0, 0, 0, 0)
    return sprite


def build_body(stage: str, src: Path, dest: Path) -> None:
    """Full-body pill art from the same portrait, cleaned of baked background."""
    im = Image.open(src).convert("RGB")
    sprite = remove_background(im)
    bbox = sprite.getbbox()
    if bbox:
        sprite = sprite.crop(bbox)
    sprite = clean_body(sprite)
    sprite = fit_portrait(sprite, BODY_TARGET, BODY_PAD)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sprite.save(dest)
    print(f"{dest.name:34s} edge alpha {edge_report(sprite)}")



def build_bodies() -> None:
    sources = {
        "bayi": ROOT / "mobile" / "assets" / "3d" / "momo_bayi.png",
        "remaja": ROOT / "mobile" / "assets" / "3d" / "momo_remaja.png",
        "dewasa": ROOT / "mobile" / "assets" / "3d" / "momo_dewasa.png",
    }
    tiles: list[Image.Image] = []
    for stage, src in sources.items():
        dest = OUT / f"pill_body_{stage}.png"
        build_body(stage, src, dest)
        tiles.append(Image.open(dest))
    width, height = BODY_TARGET
    preview = Image.new("RGB", (width * 3 + 40, height + 40), (24, 24, 27))
    for i, tile in enumerate(tiles):
        preview.paste(tile, (10 + i * (width + 10), 20), tile)
    path = ROOT / "tools" / "pill_body_preview.png"
    preview.save(path)
    print(f"preview -> {path}")


def main(argv: list[str]) -> int:
    if "--bodies" in argv:
        build_bodies()
        return 0
    sources = {
        "bayi": ROOT / "mobile" / "assets" / "3d" / "momo_bayi.png",
        "remaja": ROOT / "mobile" / "assets" / "3d" / "momo_remaja.png",
        "dewasa": ROOT / "mobile" / "assets" / "3d" / "momo_dewasa.png",
    }
    tiles: list[Image.Image] = []
    for stage, src in sources.items():
        dest = OUT / f"pill_mascot_{stage}.png"
        build(stage, src, dest, CROPS[stage])
        tiles.append(Image.open(dest))

    preview = Image.new("RGB", (TARGET * 3 + 40, TARGET + 40), (24, 24, 27))
    for i, t in enumerate(tiles):
        preview.paste(t, (10 + i * (TARGET + 10), 20), t)
    preview.save(PREVIEW)
    print(f"preview -> {PREVIEW}")

    moods = ["fresh", "tired", "critical"]
    grid = Image.new("RGB", (TARGET * 3 + 40, TARGET * 3 + 40), (24, 24, 27))
    for row, stage in enumerate(sources):
        for col, mood in enumerate(moods):
            if mood == "fresh":
                dest = OUT / f"pill_mascot_{stage}.png"
            else:
                src = ROOT / EXPRESSIONS[(stage, mood)]
                dest = OUT / f"pill_mascot_{stage}_{mood}.png"
                build(stage, src, dest, None)
            tile = Image.open(dest)
            grid.paste(tile, (10 + col * (TARGET + 10), 10 + row * (TARGET + 10)), tile)
    grid_path = ROOT / "tools" / "pill_sprite_grid.png"
    grid.save(grid_path)
    print(f"grid -> {grid_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
