import numpy as np
import pytest

from pulselens.analysis.landmarks import FACE_MODEL
from pulselens.analysis.vision.face import regions_from_landmarks, to_pixels
from pulselens.analysis.vision.frames import dhash, region_means
from pulselens.analysis.vision.linearize import linear_to_srgb, srgb_to_linear
from pulselens.analysis.vision.pose import rotation_y, yaw_pitch
from tests.fixtures.synth import H, W, landmarks_478, synthetic_landmarks


def test_srgb_to_linear_endpoints_and_mid_grey() -> None:
    assert srgb_to_linear(np.array([0.0, 1.0])).tolist() == [0.0, 1.0]
    assert srgb_to_linear(np.array([0.5]))[0] == pytest.approx(0.214, abs=1e-3)
    x = np.linspace(0, 1, 101)
    assert np.allclose(linear_to_srgb(srgb_to_linear(x)), x)


def test_srgb_to_linear_reads_uint8_as_0_to_255() -> None:
    out = srgb_to_linear(np.array([[[0, 128, 255]]], dtype=np.uint8))
    assert out[0, 0, 0] == 0.0 and out[0, 0, 2] == 1.0
    assert out[0, 0, 1] == pytest.approx(srgb_to_linear(np.array([128 / 255]))[0])


def test_neck_box_is_below_the_chin_and_0_6_face_widths_wide() -> None:
    r = regions_from_landmarks(synthetic_landmarks(chin_y=150), W, H)
    # face 80 wide, 110 tall: neck 0.6 widths wide, from 0.05 to 0.45 heights below the chin
    assert r.neck.x1 - r.neck.x0 == pytest.approx(0.6 * 80)
    assert (r.neck.y0, r.neck.y1) == pytest.approx((150 + 5.5, 150 + 49.5))
    assert r.neck.y0 > 150
    assert r.neck_coverage == pytest.approx(1.0)


def test_neck_box_half_outside_the_frame_has_coverage_one_half() -> None:
    # nominal neck from chin + 5.5 to chin + 49.5 (44 px); half of it below the frame edge
    chin_y = H - 5.5 - 22
    r = regions_from_landmarks(synthetic_landmarks(chin_y=chin_y), W, H)
    assert r.neck.y1 == H
    assert r.neck_coverage == pytest.approx(0.5)


def test_skin_regions_avoid_eyes_and_lips_and_cheeks_split_by_image_side() -> None:
    r = regions_from_landmarks(synthetic_landmarks(), W, H)
    for b in r.skin:
        assert r.face_box.x0 <= b.x0 < b.x1 <= r.face_box.x1
        assert r.face_box.y0 <= b.y0 < b.y1 <= r.face_box.y1
    for cheek in (r.left_cheek, r.right_cheek):
        assert cheek.y0 > 40 + 44 and cheek.y1 < 40 + 88
    assert r.left_cheek.x1 <= 160 <= r.right_cheek.x0


def test_the_478_point_cache_gives_the_same_regions() -> None:
    a = regions_from_landmarks(synthetic_landmarks(), W, H)
    b = regions_from_landmarks(to_pixels(landmarks_478(), W, H), W, H)
    assert a == b


def test_region_means_and_background_mask() -> None:
    img = np.full((H, W, 3), 0.2)
    img[40:150, 120:200] = 0.6  # face
    img[150:, 130:190] = 0.9  # neck and body
    means = region_means(img, regions_from_landmarks(synthetic_landmarks(), W, H))
    assert means["skin"][0] == pytest.approx([0.6] * 3)
    assert means["left_cheek"][0] == pytest.approx([0.6] * 3)
    assert means["neck"][0] == pytest.approx([0.9] * 3)
    assert means["background"][0] == pytest.approx([0.2] * 3)


def test_region_means_without_a_face_measure_only_the_background() -> None:
    means = region_means(np.full((H, W, 3), 0.3), None)
    assert means["skin"][1] == 0 and means["neck"][1] == 0
    assert np.isnan(means["skin"][0]).all()
    assert means["background"][0] == pytest.approx([0.3] * 3)


def test_dhash_is_stable_and_tells_frames_apart() -> None:
    rng = np.random.default_rng(0)
    a = rng.integers(0, 255, (H, W, 3), dtype=np.uint8)
    b = rng.integers(0, 255, (H, W, 3), dtype=np.uint8)
    assert dhash(a) == dhash(a.copy())
    assert dhash(a) != dhash(b)


@pytest.mark.parametrize("deg", [-40.0, -10.0, 0.0, 25.0])
def test_yaw_from_the_transformation_matrix(deg: float) -> None:
    yaw, pitch = yaw_pitch(rotation_y(deg))
    assert yaw == pytest.approx(deg)
    assert pitch == pytest.approx(0.0, abs=1e-9)


def test_yaw_of_something_that_is_not_a_matrix() -> None:
    assert yaw_pitch(np.zeros(3)) == (None, None)


@pytest.mark.skipif(not FACE_MODEL.exists(), reason="face_landmarker.task not fetched (scripts/fetch_models.py)")
def test_landmarker_runs_and_finds_no_face_in_a_blank_frame() -> None:
    from pulselens.analysis.vision.face import Landmarker

    lm = Landmarker(FACE_MODEL)
    try:
        assert lm.detect(np.full((H, W, 3), 128, dtype=np.uint8), 0.0) is None
        assert lm.detect(np.full((H, W, 3), 128, dtype=np.uint8), 0.0) is None  # same t_ms twice is fine
    finally:
        lm.close()
