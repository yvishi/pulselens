"""G11 nuisances: poor capture must lead to an abstain or nothing, never a flag (AGENTS.md rule 3)."""

import cv2
import numpy as np
import pytest

from pulselens.analysis import analyze
from pulselens.analysis.checks import sensor_stream
from pulselens.analysis.vision.frames import jpeg_quality, region_means
from pulselens.analysis.vision.linearize import srgb_to_linear
from tests.fixtures.synth import H, W

NUISANCES = {
    "tube_light_15fps": {"fps": 15.0, "flicker": 0.3},  # a 100 Hz ripple sampled at 15 fps aliases to 5 Hz
    "tube_light_30fps": {"flicker": 0.3},
    "glare": {"glare": True},  # a blown-out band across the forehead
    "glare_15fps": {"glare": True, "fps": 15.0},
    "neck_hidden_half": {"chin_y_late": H - 4},  # the neck leaves the frame for the second half
    "heavy_jpeg": {"jpeg_quality": 50},
    "heavy_jpeg_15fps": {"jpeg_quality": 50, "fps": 15.0},
    "heavy_jpeg_real_noise": {"jpeg_quality": 50, "noise": 0.02},
}


@pytest.mark.parametrize("kw", NUISANCES.values(), ids=NUISANCES.keys())
def test_poor_capture_is_never_flagged(synth, kw) -> None:
    results = analyze(synth.session(kind="genuine", **kw))
    flagged = [(r.check_id, r.reason_codes, r.explanation) for r in results if r.flag]
    assert not flagged


def test_heavy_jpeg_abstains_the_noise_comparison(synth) -> None:
    r = {x.check_id: x for x in analyze(synth.session(kind="genuine", jpeg_quality=50))}["sensor.regions"]
    assert r.status == "abstain" and r.reason_codes == ["quality.heavy_compression"]
    assert r.features["jpeg_quality"] == pytest.approx(50, abs=3)


@pytest.mark.parametrize("q", [30, 50, 75, 90, 95])
def test_jpeg_quality_is_read_from_the_quantisation_table(q: int) -> None:
    img = np.random.default_rng(q).integers(0, 255, (48, 64, 3), dtype=np.uint8)
    data = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])[1].tobytes()
    assert jpeg_quality(data) == pytest.approx(q, abs=2)
    assert jpeg_quality(b"not a jpeg") is None


def test_blown_out_pixels_are_left_out_of_a_region_mean() -> None:
    from pulselens.analysis.vision.face import regions_from_landmarks
    from tests.fixtures.synth import synthetic_landmarks

    regions = regions_from_landmarks(synthetic_landmarks(), W, H)
    img = np.full((H, W, 3), 120, dtype=np.uint8)
    rows, cols = regions.forehead.slices()
    img[rows, cols] = 255  # the whole forehead blown out; the cheeks stay clean
    skin = region_means(img, regions)["skin"][0]
    assert skin == pytest.approx(np.full(3, srgb_to_linear(np.array(120 / 255))), rel=1e-9)


def test_a_region_mostly_blown_out_keeps_its_pixels_so_the_gate_sees_it() -> None:
    from pulselens.analysis.vision.face import regions_from_landmarks
    from tests.fixtures.synth import synthetic_landmarks

    regions = regions_from_landmarks(synthetic_landmarks(), W, H)
    img = np.full((H, W, 3), 255, dtype=np.uint8)
    assert region_means(img, regions)["skin"][0] == pytest.approx(np.ones(3))


def test_exact_repeats_still_count_when_every_frame_changes_little(synth) -> None:
    ctx = synth.context(kind="genuine", turn=None, jpeg_quality=50)
    ctx.mad_prev[10::10] = 0.0  # a relay repeating every 10th frame exactly
    ctx.hamming_prev[10::10] = 0
    r = {x.check_id: x for x in sensor_stream.run(ctx)}["sensor.duplicates"]
    assert r.flag and r.features["dup_share"] == pytest.approx(0.1, abs=0.01)
