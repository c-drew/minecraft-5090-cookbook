#!/usr/bin/env python3
"""CPU replay of the runtime loader/kernel from actual pre-RR GPU image readbacks.

This checks integration arithmetic, not whether filtering improves reconstruction.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import numpy as np

spec = importlib.util.spec_from_file_location('raw_capture', Path(__file__).with_name('check-raw-light-capture.py'))
raw_capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(raw_capture)


def replay(path):
    metadata, a, _ = raw_capture.read_capture(path)
    raw = a['reconstruction'][0, :, :, :3].astype(np.float32)
    transmission = a['reconstruction'][1, :, :, :3].astype(np.float32)
    albedo = (a['diffuse_albedo'][0, :, :, :3].astype(np.float32) + a['specular_albedo'][0, :, :, :3]) / np.float32(255)
    albedo = np.maximum(albedo, np.float32(.001))
    position = a['primary_position'][0, :, :, :3]
    geometric = a['primary_geometry'][0, :, :, :3].copy()
    shading = a['normal_roughness'][0, :, :, :3].astype(np.float32)
    roughness = a['normal_roughness'][0, :, :, 3].astype(np.float32)
    g_len = np.sum(geometric * geometric, axis=2)
    s_len = np.sum(shading * shading, axis=2)
    valid = ((a['reconstruction'][0, :, :, 3] > .5) & np.isfinite(raw).all(2) & (raw >= 0).all(2) &
             np.isfinite(position).all(2) & np.isfinite(geometric).all(2) & np.isfinite(shading).all(2) &
             np.isfinite(roughness) & (g_len > 1e-6) & (s_len > 1e-6))
    geometric /= np.sqrt(np.maximum(g_len, 1e-20))[:, :, None]
    shading /= np.sqrt(np.maximum(s_len, 1e-20))[:, :, None]
    lighting = np.where(valid[:, :, None], raw / albedo, 0)
    numerator = lighting.copy()
    denominator = np.ones(raw.shape[:2], np.float32)
    height, width = raw.shape[:2]
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            c = (slice(max(0, -dy), min(height, height - dy)), slice(max(0, -dx), min(width, width - dx)))
            n = (slice(max(0, dy), min(height, height + dy)), slice(max(0, dx), min(width, width + dx)))
            delta = position[n] - position[c]
            plane = np.maximum(np.abs(np.sum(delta * geometric[c], 2)), np.abs(np.sum(delta * geometric[n], 2)))
            geometric_dot = np.sum(geometric[c] * geometric[n], 2)
            normal_weight = np.clip(np.sum(shading[c] * shading[n], 2), 0, 1) ** np.float32(32)
            spatial_weight = np.float32((1 if dx == 0 else .5) * (1 if dy == 0 else .5))
            weight = spatial_weight * normal_weight * np.exp2(-plane * 200 - np.abs(roughness[c] - roughness[n]) * 16)
            accept = valid[c] & valid[n] & (plane <= .04) & (geometric_dot >= .95)
            weight = np.where(accept, weight, 0)
            numerator[c] += weight[:, :, None] * lighting[n]
            denominator[c] += weight
    reconstructed = albedo * (numerator / denominator[:, :, None])
    reconstructed = np.where(np.isfinite(reconstructed).all(2)[:, :, None], reconstructed, raw)
    before = a['hdr_before'][0, :, :, :3].astype(np.float32)
    after = a['hdr_after'][0, :, :, :3].astype(np.float32)
    composed = before + (reconstructed - raw) * transmission
    write = (valid & (a['reconstruction'][1, :, :, 3] > .5) & np.isfinite(transmission).all(2) &
             np.isfinite(composed).all(2) & (composed <= 65504).all(2))
    expected = np.where(write[:, :, None], np.maximum(composed, 0), before).astype(np.float16).astype(np.float32)
    error = np.abs(expected - after)
    ulp = np.abs(np.spacing(after.astype(np.float16))).astype(np.float32)
    unexpected = (error > np.maximum(ulp * 3, 2e-5)).any(2)
    luminance_weights = np.array([.2126, .7152, .0722], np.float32)
    before_y = before @ luminance_weights
    after_y = after @ luminance_weights
    raw_y = raw @ luminance_weights
    # One-pixel bright samples on eligible surfaces and their local spread.
    stats = []
    for threshold in (.1, .5, 1, 2):
        original_bright = valid & (raw_y > threshold)
        reconstructed_bright = valid & ((reconstructed @ luminance_weights) > threshold)
        stats.append({'threshold': threshold, 'raw_indirect_bright_pixels': int(original_bright.sum()),
                      'filtered_indirect_bright_pixels': int(reconstructed_bright.sum()),
                      'new_bright_pixels': int((reconstructed_bright & ~original_bright).sum())})
    result = {'id': metadata['id'], 'shape': list(before.shape), 'eligible_loader_pixels': int(valid.sum()),
              'written_pixels': int(write.sum()), 'unexpected_pixels': int(unexpected.sum()),
              'fraction_exact_half_channels': float((error == 0).mean()),
              'max_error': float(error.max()), 'mean_error': float(error.mean()), 'bright_sample_spread': stats,
              'mean_hdr_luminance_before': float(before_y.mean()), 'mean_hdr_luminance_after': float(after_y.mean()),
              'mean_raw_indirect_eligible': float(raw_y[valid].mean()),
              'mean_filtered_indirect_eligible': float((reconstructed @ luminance_weights)[valid].mean())}
    np.savez_compressed(path / 'replay.npz', reconstructed=reconstructed.astype(np.float16), valid=valid,
                        error=error.astype(np.float16), unexpected=unexpected)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    results = [replay(p.parent) for p in sorted(args.directory.glob('*/manifest.json'))]
    (args.directory / 'replay.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))
