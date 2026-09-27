#!/usr/bin/env python3
"""Fetch the pinned NVIDIA evaluation asset and preserve its separate license.

The asset is not distributed by this cookbook or covered by its GPL license.
Requires Pillow. OUTPUT is the Advanced shader-pack directory.
"""
import argparse
import hashlib
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile
from PIL import Image

PIN = '48b2839e4d8b7f0202ac72c6b0ae720d235a5b8b'
BASE = f'https://raw.githubusercontent.com/NVIDIA-RTX/STBN/{PIN}/'
ZIP_SHA = 'f262aaa79704b913ad1ac22b11674931c5c16a788688f8ce49ec43d59eb5c747'
LICENSE_SHA = 'a897cb00670ea9d1465e3b1428f9fb6155a43ff226bc874c00b122d8049446f8'
MASK_SHA = '19059f90a232018e4de3a0439333ac191d3c032a182d6e37c93fb26e88521b85'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output', type=Path)
parser.add_argument('--archive', type=Path, help='Use an already downloaded pinned STBN.zip')
parser.add_argument('--license', type=Path, help='Use the corresponding original License.txt')
args = parser.parse_args()

def fetch(path, relative, expected):
    data = path.read_bytes() if path else urlopen(BASE + relative, timeout=60).read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError(f'Unexpected bytes for {relative}')
    return data

license_bytes = fetch(args.license, 'License.txt', LICENSE_SHA)
archive = fetch(args.archive, 'Assets/STBN.zip', ZIP_SHA)
frames = []
with ZipFile(BytesIO(archive)) as package:
    for index in range(64):
        with Image.open(BytesIO(package.read(f'STBN/stbn_vec3_2Dx1D_128x128x64_{index}.png'))) as im:
            assert im.size == (128, 128)
            frames.append(im.convert('RGBA').tobytes())
mask = b''.join(frames)
assert len(mask) == 64 * 128 * 128 * 4
assert hashlib.sha256(mask).hexdigest() == MASK_SHA
assets = args.output / 'assets'
assets.mkdir(parents=True, exist_ok=True)
for name, data in [('STBN-License.txt', license_bytes), ('stbn-vec3.rgba8', mask)]:
    target = assets / name
    if target.exists() and target.read_bytes() != data:
        raise RuntimeError(f'Refusing to overwrite different asset: {target}')
    target.write_bytes(data)
print(f'Wrote pinned evaluation mask and NVIDIA license to {assets}')
