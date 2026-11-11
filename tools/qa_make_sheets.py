#!/usr/bin/env python3
"""Compose Blender QA frames into labelled contact sheets."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONT = "C:/Windows/Fonts/arialbd.ttf"
FONT_SMALL = "C:/Windows/Fonts/arial.ttf"


def main(frames_dir, out_dir, title, per_sheet=5, frames=4):
    frames_dir = Path(frames_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(frames_dir.glob("*__0.png"))
    clips = [f.name.split("__")[0] for f in files]
    if not clips:
        raise SystemExit(f"no frames in {frames_dir}")
    cell = 320
    label_w = 160
    head_h = 36
    pad = 8
    font = ImageFont.truetype(FONT, 15)
    font_small = ImageFont.truetype(FONT_SMALL, 13)
    font_title = ImageFont.truetype(FONT, 18)
    sheets = []
    for start in range(0, len(clips), per_sheet):
        group = clips[start : start + per_sheet]
        w = label_w + frames * cell + pad * 2
        h = head_h + len(group) * (cell + 24) + pad * 2
        img = Image.new("RGB", (w, h), (24, 26, 30))
        d = ImageDraw.Draw(img)
        d.text((pad, 8), f"{title} - clips {start + 1}-{start + len(group)} of {len(clips)}", font=font_title, fill=(240, 240, 240))
        for row, clip in enumerate(group):
            y = head_h + pad + row * (cell + 24)
            d.text((pad, y + cell // 2 - 10), clip, font=font, fill=(255, 220, 120))
            for f in range(frames):
                path = frames_dir / f"{clip}__{f}.png"
                if not path.exists():
                    continue
                im = Image.open(path).convert("RGB").resize((cell, cell))
                img.paste(im, (label_w + pad + f * cell, y))
            d.text((label_w + pad, y + cell + 3), "0%      33%       66%      100%", font=font_small, fill=(180, 180, 190))
        out = out_dir / f"{title}_sheet_{start // per_sheet + 1}.png"
        img.save(out)
        sheets.append(out)
        print(out)
    return sheets


if __name__ == "__main__":
    frames_dir, out_dir, title = sys.argv[1:4]
    main(frames_dir, out_dir, title)
