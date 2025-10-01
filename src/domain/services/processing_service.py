from __future__ import annotations

import numpy as np


class ProcessingService:
    """Pure NumPy image processing. Inputs and outputs are float32 arrays normalized to [0, 1].

    Channel convention:
    - Grayscale: (H, W)
    - RGB: (H, W, 3)
    """

    # Brightness: I_out = I_in + factor
    @staticmethod
    def adjust_brightness(matrix: np.ndarray, factor: float) -> np.ndarray:
        out = np.clip(matrix.astype(np.float32) + float(factor), 0.0, 1.0)
        return out.astype(np.float32)

    # Logarithmic contrast: I_out = k * log10(1 + I_in)
    @staticmethod
    def adjust_log_contrast(matrix: np.ndarray, k: float) -> np.ndarray:
        mat = matrix.astype(np.float32)
        out = np.clip(float(k) * np.log10(1.0 + mat), 0.0, 1.0)
        return out.astype(np.float32)

    # Exponential contrast: I_out = k * exp(I_in - 1)
    @staticmethod
    def adjust_exp_contrast(matrix: np.ndarray, k: float) -> np.ndarray:
        mat = matrix.astype(np.float32)
        out = np.clip(float(k) * np.exp(mat - 1.0), 0.0, 1.0)
        return out.astype(np.float32)

    # Invert: I_out = 1 - I_in
    @staticmethod
    def invert_color(matrix: np.ndarray) -> np.ndarray:
        return (1.0 - matrix.astype(np.float32)).astype(np.float32)

    # Grayscale (Average): (R + G + B) / 3
    @staticmethod
    def grayscale_average(matrix: np.ndarray) -> np.ndarray:
        mat = matrix.astype(np.float32)
        if mat.ndim == 3 and mat.shape[2] >= 3:
            return np.mean(mat[..., :3], axis=2).astype(np.float32)
        return mat

    # Grayscale (Luminosity): 0.299*R + 0.587*G + 0.114*B
    @staticmethod
    def grayscale_luminosity(matrix: np.ndarray) -> np.ndarray:
        mat = matrix.astype(np.float32)
        if mat.ndim == 3 and mat.shape[2] >= 3:
            weights = np.array([0.299, 0.587, 0.114], dtype=np.float32)
            return np.dot(mat[..., :3], weights).astype(np.float32)
        return mat

    # Grayscale (Midgray): (max(R,G,B) + min(R,G,B)) / 2
    @staticmethod
    def grayscale_midgray(matrix: np.ndarray) -> np.ndarray:
        mat = matrix.astype(np.float32)
        if mat.ndim == 3 and mat.shape[2] >= 3:
            mx = np.max(mat[..., :3], axis=2)
            mn = np.min(mat[..., :3], axis=2)
            return ((mx + mn) / 2.0).astype(np.float32)
        return mat

    # Binarize: I_out = 1 if I >= threshold else 0
    @staticmethod
    def binarize(matrix: np.ndarray, threshold: float) -> np.ndarray:
        return (matrix.astype(np.float32) >= float(threshold)).astype(np.float32)

    # Extract CMY channels from RGB: C=1-R, M=1-G, Y=1-B
    @staticmethod
    def extract_cmy_channels(
        matrix: np.ndarray,
    ) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
        mat = matrix.astype(np.float32)
        if mat.ndim == 3 and mat.shape[2] >= 3:
            cyan = 1.0 - mat[..., 0]
            magenta = 1.0 - mat[..., 1]
            yellow = 1.0 - mat[..., 2]
            return cyan.astype(np.float32), magenta.astype(np.float32), yellow.astype(np.float32)
        return None, None, None

    # Translate image by (dx, dy). Positive dx moves right, dy moves down. Fill with zeros.
    @staticmethod
    def translate(matrix: np.ndarray, dx: int, dy: int) -> np.ndarray:
        mat = matrix.astype(np.float32)
        h, w = mat.shape[:2]
        if mat.ndim == 2:
            out = np.zeros_like(mat)
        else:
            out = np.zeros((h, w, mat.shape[2]), dtype=np.float32)
        # compute source and destination ranges
        x_src_start = max(0, -dx)
        y_src_start = max(0, -dy)
        x_dst_start = max(0, dx)
        y_dst_start = max(0, dy)
        x_len = min(w - x_dst_start, w - x_src_start)
        y_len = min(h - y_dst_start, h - y_src_start)
        if x_len <= 0 or y_len <= 0:
            return out
        if mat.ndim == 2:
            out[y_dst_start : y_dst_start + y_len, x_dst_start : x_dst_start + x_len] = mat[
                y_src_start : y_src_start + y_len, x_src_start : x_src_start + x_len
            ]
        else:
            out[y_dst_start : y_dst_start + y_len, x_dst_start : x_dst_start + x_len, :] = mat[
                y_src_start : y_src_start + y_len, x_src_start : x_src_start + x_len, :
            ]
        return out

    # Rotate by angle degrees around image center using nearest-neighbor sampling.
    # Output keeps same size.
    @staticmethod
    def rotate(matrix: np.ndarray, angle: float) -> np.ndarray:
        mat = matrix.astype(np.float32)
        h, w = mat.shape[:2]
        if mat.ndim == 2:
            out = np.zeros_like(mat)
            channels = 1
        else:
            out = np.zeros((h, w, mat.shape[2]), dtype=np.float32)
            channels = mat.shape[2]
        rad = np.deg2rad(angle)
        cos_a = np.cos(rad)
        sin_a = np.sin(rad)
        cx = (w - 1) / 2.0
        cy = (h - 1) / 2.0
        # For each destination pixel, map back to source
        ys, xs = np.indices((h, w))
        x_rel = xs - cx
        y_rel = ys - cy
        x_src = cos_a * x_rel + sin_a * y_rel + cx
        y_src = -sin_a * x_rel + cos_a * y_rel + cy
        x_src_round = np.rint(x_src).astype(int)
        y_src_round = np.rint(y_src).astype(int)
        valid = (x_src_round >= 0) & (x_src_round < w) & (y_src_round >= 0) & (y_src_round < h)
        if channels == 1:
            out[valid] = mat[y_src_round[valid], x_src_round[valid]]
        else:
            out[valid, :] = mat[y_src_round[valid], x_src_round[valid], :]
        return out

    # Crop region [y_start:y_end, x_start:x_end]
    @staticmethod
    def crop(matrix: np.ndarray, x_start: int, x_end: int, y_start: int, y_end: int) -> np.ndarray:
        return matrix.astype(np.float32)[y_start:y_end, x_start:x_end]

    # Reduce resolution by subsampling every `factor` pixels
    @staticmethod
    def reduce_resolution(matrix: np.ndarray, factor: int) -> np.ndarray:
        factor = int(factor)
        if factor <= 0:
            raise ValueError("factor must be > 0")
        mat = matrix.astype(np.float32)
        if mat.ndim == 2:
            return mat[::factor, ::factor]
        return mat[::factor, ::factor, :]

    # Enlarge region by integer factor using pixel replication (nearest-neighbor via kron)
    @staticmethod
    def enlarge_region(
        matrix: np.ndarray, x_start: int, x_end: int, y_start: int, y_end: int, factor: int
    ) -> np.ndarray:
        factor = int(factor)
        if factor <= 0:
            raise ValueError("factor must be > 0")
        region = matrix.astype(np.float32)[y_start:y_end, x_start:x_end]
        if region.ndim == 3:
            return np.kron(region, np.ones((factor, factor, 1), dtype=np.float32)).astype(
                np.float32
            )
        return np.kron(region, np.ones((factor, factor), dtype=np.float32)).astype(np.float32)

    # Merge images with transparency: out = (1 - a) * img1 + a * img2.
    # Resize img2 to img1 shape if needed via simple nearest-neighbor.
    @staticmethod
    def merge_images(img1: np.ndarray, img2: np.ndarray, transparency: float) -> np.ndarray:
        a = float(np.clip(transparency, 0.0, 1.0))
        a1 = 1.0 - a
        im1 = img1.astype(np.float32)
        im2 = img2.astype(np.float32)
        # reshape img2 to img1 shape with nearest neighbor if needed
        if im1.shape != im2.shape:
            im2 = ProcessingService._resize_nearest(im2, im1.shape[:2])
            if im1.ndim == 3 and im2.ndim == 2:
                im2 = np.repeat(im2[..., None], 3, axis=2)
            if im1.ndim == 2 and im2.ndim == 3:
                im2 = ProcessingService.grayscale_luminosity(im2)
        out = np.clip(a1 * im1 + a * im2, 0.0, 1.0)
        return out.astype(np.float32)

    # Calculate histogram per channel with 256 bins over [0, 1].
    # Returns dict with keys: "bins", "hist".
    @staticmethod
    def calculate_histogram(matrix: np.ndarray) -> dict[str, np.ndarray]:
        mat = np.clip(matrix.astype(np.float32), 0.0, 1.0)
        bins = np.linspace(0.0, 1.0, 257, dtype=np.float32)
        if mat.ndim == 2:
            hist, _ = np.histogram(mat, bins=bins)
            return {"bins": bins, "hist": hist.astype(np.int64)}
        # RGB or multi-channel: compute per-channel and stack
        chans = mat.shape[2]
        hists = []
        for c in range(chans):
            h, _ = np.histogram(mat[..., c], bins=bins)
            hists.append(h.astype(np.int64))
        hist_arr = np.stack(hists, axis=0)
        return {"bins": bins, "hist": hist_arr}

    # --------- helpers ---------
    @staticmethod
    def _resize_nearest(img: np.ndarray, target_hw: tuple[int, int]) -> np.ndarray:
        th, tw = target_hw
        h, w = img.shape[:2]
        if h == th and w == tw:
            return img
        # create index grid mapping target->source
        ys = (np.arange(th) * (h / th)).astype(np.int64)
        xs = (np.arange(tw) * (w / tw)).astype(np.int64)
        ys = np.clip(ys, 0, h - 1)
        xs = np.clip(xs, 0, w - 1)
        if img.ndim == 2:
            return img[ys[:, None], xs[None, :]].astype(np.float32)
        return img[ys[:, None], xs[None, :], :].astype(np.float32)
