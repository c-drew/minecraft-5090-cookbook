#!/usr/bin/env python3
"""Compare benchmark screenshots: RMSE and mean luminance difference against a reference, plus an
optional side-by-side crop sheet.

Usage: tools/img-diff.py REF.png OTHER.png [OTHER2.png ...] [--sheet OUT.png] [--crop x,y,w,h]
Screenshots are the F2 captures the bench takes at the start of each measurement; the HUD rows
(hotbar) are excluded.
"""
import argparse

import numpy as np
from PIL import Image, ImageDraw

parser = argparse.ArgumentParser()
parser.add_argument('ref')
parser.add_argument('others', nargs='+')
parser.add_argument('--sheet')
parser.add_argument('--crop', help='x,y,w,h in pixels of the full screenshot')
args = parser.parse_args()


def load(path):
    img = np.asarray(Image.open(path).convert('RGB'), dtype=np.float32) / 255.0
    return img[: int(img.shape[0] * 0.88)]  # drop the hotbar


def luminance(img):
    return img @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


ref = load(args.ref)
print(f'{"image":60} {"rmse%":>7} {"lum%":>7}')
for path in args.others:
    img = load(path)
    rmse = float(np.sqrt(np.mean((img - ref) ** 2))) * 100
    lum = (float(luminance(img).mean()) / max(float(luminance(ref).mean()), 1e-6) - 1) * 100
    print(f'{path[-60:]:60} {rmse:7.2f} {lum:+7.2f}')

if args.sheet:
    x, y, w, h = map(int, (args.crop or '0,0,1280,720').split(','))
    tiles = [Image.open(p).convert('RGB').crop((x, y, x + w, y + h)) for p in [args.ref, *args.others]]
    sheet = Image.new('RGB', (w, h * len(tiles)))
    for i, (tile, path) in enumerate(zip(tiles, [args.ref, *args.others])):
        sheet.paste(tile, (0, i * h))
        ImageDraw.Draw(sheet).text((8, i * h + 8), path.rsplit('/', 1)[-1], fill=(255, 0, 0))
    sheet.save(args.sheet)
    print('sheet', args.sheet)
