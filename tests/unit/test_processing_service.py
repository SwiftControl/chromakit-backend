import numpy as np

from src.domain.services.processing_service import ProcessingService as PS


def test_brightness_clip():
    img = np.array([[0.0, 0.5], [0.9, 1.0]], dtype=np.float32)
    out = PS.adjust_brightness(img, 0.3)
    assert out.dtype == np.float32
    assert np.isclose(out[0, 0], 0.3)
    assert np.isclose(out[1, 1], 1.0)


def test_invert_color():
    img = np.array([[0.0, 0.25], [0.75, 1.0]], dtype=np.float32)
    out = PS.invert_color(img)
    assert np.allclose(out, 1.0 - img)


def test_rotate_90_nearest_keeps_shape():
    # simple 2x3 image with a pattern
    img = np.array(
        [
            [0.0, 0.5, 1.0],
            [0.2, 0.4, 0.6],
        ],
        dtype=np.float32,
    )
    out = PS.rotate(img, 90)
    assert out.shape == img.shape


def test_histogram_gray_and_rgb():
    gray = np.linspace(0, 1, 16, dtype=np.float32).reshape(4, 4)
    hist_g = PS.calculate_histogram(gray)
    assert "bins" in hist_g and "hist" in hist_g
    assert hist_g["hist"].sum() == 16

    rgb = np.stack([gray, gray, gray], axis=-1)
    hist_r = PS.calculate_histogram(rgb)
    assert hist_r["hist"].shape[0] == 3
    assert hist_r["hist"].sum() == 16 * 3

