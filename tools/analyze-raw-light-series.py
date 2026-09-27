#!/usr/bin/env python3
"""Decompose stationary pre-RR luminance variance after aligning camera jitter.

Residual means HDR minus weighted continuation. It is not assumed to be only
direct light. Pixel and 16x16 block statistics describe input fluctuation,
not reconstruction quality, perception, or a temporal convergence rate.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import numpy as np

spec = importlib.util.spec_from_file_location('raw', Path(__file__).with_name('check-raw-light-capture.py'))
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)
Y = np.array([.2126, .7152, .0722], np.float32)
NAMES = ['hdr', 'continuation', 'residual', 'direct_image', 'residual_minus_direct',
         'diffuse_albedo_y', 'normal_x', 'normal_y', 'normal_z',
         'source_hit_direct', 'source_hit_other', 'source_cache', 'source_miss']
CROPS = {'turn': (10, 15, 250, 200), 'return': (400, 15, 635, 195)}


def align_crop(value, jitter, crop):
    x0, y0, x1, y1 = crop
    xx = np.arange(x0, x1, dtype=np.float32) - jitter[0]
    yy = np.arange(y0, y1, dtype=np.float32) - jitter[1]
    ix = np.floor(xx).astype(np.int32)
    iy = np.floor(yy).astype(np.int32)
    assert ix.min() >= 0 and iy.min() >= 0 and ix.max() + 1 < value.shape[1] and iy.max() + 1 < value.shape[0]
    fx, fy = xx - ix, yy - iy
    low = value[iy[:, None], ix[None, :]] * (1 - fx[None, :]) + value[iy[:, None], ix[None, :] + 1] * fx[None, :]
    high = value[iy[:, None] + 1, ix[None, :]] * (1 - fx[None, :]) + value[iy[:, None] + 1, ix[None, :] + 1] * fx[None, :]
    return low * (1 - fy[:, None]) + high * fy[:, None]


def statistics(values, mask):
    x = values[:, mask, :5].astype(np.float64)
    means = x.mean(axis=(0, 1))
    variances = x.var(axis=0, ddof=1).mean(axis=0)
    covariance = float((variances[0] - variances[1] - variances[2]) / 2)
    sources = values[:, mask, 9:13].astype(np.float64)
    centered = sources - sources.mean(axis=0, keepdims=True)
    covariance_sources = np.einsum('tpi,tpj->ij', centered, centered) / ((len(values) - 1) * mask.sum())
    source_total_variance = float(covariance_sources.sum())
    return {'locations': int(mask.sum()), 'mean_luminance': dict(zip(NAMES[:5], means.tolist())),
            'mean_temporal_variance': dict(zip(NAMES[:5], variances.tolist())),
            'continuation_residual_covariance': covariance,
            'variance_over_hdr_variance': dict(zip(NAMES[:5], (variances / max(variances[0], 1e-30)).tolist())),
            'normalized_hdr_rms': float(np.sqrt(variances[0]) / max(means[0], 1e-30)),
            'unweighted_continuation_sources': {
                'names': NAMES[9:13], 'mean': sources.mean(axis=(0, 1)).tolist(),
                'covariance_matrix': covariance_sources.tolist(),
                'variance_of_sum': source_total_variance,
                'component_variance_over_sum_variance': (covariance_sources.diagonal() / max(source_total_variance, 1e-30)).tolist()}}


def analyze(root, name):
    paths = sorted((root / 'series' / name).glob('*/manifest.json'))
    assert len(paths) >= 8
    frames, eligibility, manifests, validations = [], [], [], []
    reference = None
    for p in paths:
        m, a, sentinels = capture.read_capture(p.parent)
        if reference is None:
            reference = m
        assert m['camera'] == reference['camera'] and m['view_column_major'] == reference['view_column_major']
        assert (p.parent / 'hdr_before.bin').read_bytes() == (p.parent / 'hdr_after.bin').read_bytes()
        hdr = a['hdr_before'][0, :, :, :3].astype(np.float32) @ Y
        recon = a['reconstruction'].astype(np.float32)
        indirect = (recon[0, :, :, :3] * recon[1, :, :, :3]) @ Y
        direct = a['direct'][0, :, :, :3].astype(np.float32) @ Y
        residual = hdr - indirect
        albedo = (a['diffuse_albedo'][0, :, :, :3].astype(np.float32) / 255) @ Y
        normal = a['normal_roughness'][0, :, :, :3].astype(np.float32)
        h, w = hdr.shape
        crop = tuple(int(round(v * (w / 640 if i % 2 == 0 else h / 360))) for i, v in enumerate(CROPS[name]))
        fields = [hdr, indirect, residual, direct, residual - direct, albedo,
                  normal[:, :, 0], normal[:, :, 1], normal[:, :, 2]]
        sources = a['indirect_surface'][0]
        source_error = np.abs(sources.sum(-1) - recon[0, :, :, :3] @ Y)
        assert not ((recon[0, :, :, 3] > .5) &
                    (source_error > np.maximum(np.abs(recon[0, :, :, :3] @ Y) * .002, 1e-6))).any()
        fields.extend(sources[:, :, i] for i in range(4))
        values = np.stack([align_crop(v, m['jitter'], crop) for v in fields], axis=-1)
        valid = align_crop((recon[0, :, :, 3] > .5).astype(np.float32), m['jitter'], crop) > .99999
        assert np.isfinite(values[valid]).all()
        frames.append(values)
        eligibility.append(valid)
        manifests.append({k: m[k] for k in ['id', 'frame', 'jitter', 'capture_steady_ns']})
        validations.append({'id': m['id'], 'sentinels': sentinels, 'hdr_exact_identity': True})
    values = np.stack(frames)
    common = np.logical_and.reduce(eligibility)
    albedo_mean = values[:, :, :, 5].mean(0)
    common &= albedo_mean > .02
    # Restrict the second result to samples whose aligned material guides are
    # stable, avoiding much of the residual texture/parallax resampling noise.
    albedo_relative_std = values[:, :, :, 5].std(0) / np.maximum(albedo_mean, 1e-6)
    normal_std2 = values[:, :, :, 6:9].var(0).sum(-1)
    flat = common & (albedo_relative_std < .02) & (normal_std2 < .0004)
    assert common.any() and flat.any()
    frame_count, h, w, channels = values.shape
    bh, bw = h // 16, w // 16
    block_values = values[:, :bh*16, :bw*16].reshape(frame_count, bh, 16, bw, 16, channels).mean(axis=(2, 4))
    block_mask = common[:bh*16, :bw*16].reshape(bh, 16, bw, 16).mean(axis=(1, 3)) > .99
    result = {'orientation': name, 'frames': frame_count, 'crop_input_pixels': list(crop),
              'camera_and_view_constant': True, 'samples': manifests,
              'aligned_pixels': statistics(values, common), 'stable_guide_pixels': statistics(values, flat),
              'aligned_16x16_block_means': statistics(block_values, block_mask), 'validation': validations}
    np.savez_compressed(root / f'{name}-variance.npz', mean=values.mean(0), variance=values.var(0, ddof=1),
                        common_mask=common, stable_guide_mask=flat, names=NAMES)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw_directory', type=Path)
    args = parser.parse_args()
    results = [analyze(args.raw_directory, name) for name in ('turn', 'return')]
    (args.raw_directory / 'stationary-variance.json').write_text(json.dumps(results, indent=2) + '\n')
    for row in results:
        print(json.dumps({k: v for k, v in row.items() if k not in ('samples', 'validation')}))
