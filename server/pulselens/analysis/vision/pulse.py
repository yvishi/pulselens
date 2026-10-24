"""Remote pulse (rPPG) for pulse.coherence (G10): POS on a region's mean linear RGB, then Welch spectra.

POS (Wang et al. 2017): in sliding 1.6 s windows, each channel is divided by its window mean, projected onto the plane
orthogonal to the skin tone (S1 = G - B, S2 = G + B - 2R), combined as S1 + (std S1 / std S2) S2 and overlap-added.
Spectra: Welch, 4 s Hann segments with 50% overlap, in the 0.7-4 Hz band (42-240 beats per minute).

Only two numbers leave this module: the face's pulse SNR and the face-neck coherence at the face's peak. The peak
frequency (a heart rate) and the signals (a waveform) never do (AGENTS.md: never store a heart rate or pulse waveform).
"""

from __future__ import annotations

import numpy as np

BAND_HZ = (0.7, 4.0)
POS_WINDOW_S = 1.6
SEGMENT_S = 4.0
_P = np.array([[0.0, 1.0, -1.0], [-2.0, 1.0, 1.0]])


def pos(rgb: np.ndarray, fs: float) -> np.ndarray:
    """POS pulse signal of (n, 3) linear RGB sampled evenly at `fs` Hz (no NaN)."""
    rgb = np.asarray(rgb, dtype=np.float64)
    n, win = len(rgb), max(2, int(round(POS_WINDOW_S * fs)))
    out = np.zeros(n)
    for m in range(n - win + 1):
        c = rgb[m:m + win] / rgb[m:m + win].mean(axis=0)
        s1, s2 = _P @ c.T
        sd2 = s2.std()
        h = s1 + (s1.std() / sd2 if sd2 > 0 else 0.0) * s2
        out[m:m + win] += h - h.mean()
    return out


def _welch(x: np.ndarray, y: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    nper = int(round(SEGMENT_S * fs))
    hop = nper // 2
    window = np.hanning(nper)
    sxx = syy = sxy = 0
    starts = range(0, len(x) - nper + 1, hop)
    for i in starts:
        fx = np.fft.rfft((x[i:i + nper] - x[i:i + nper].mean()) * window)
        fy = np.fft.rfft((y[i:i + nper] - y[i:i + nper].mean()) * window)
        sxx = sxx + np.abs(fx) ** 2
        syy = syy + np.abs(fy) ** 2
        sxy = sxy + fx * np.conj(fy)
    return np.fft.rfftfreq(nper, 1.0 / fs), np.asarray(sxx), np.asarray(syy), np.asarray(sxy)


def snr_and_coherence(face: np.ndarray, neck: np.ndarray, fs: float) -> tuple[float, float]:
    """(face pulse SNR in dB, face-neck magnitude-squared coherence at the face's peak, 0..1) of two evenly sampled
    pulse signals at least SEGMENT_S long. SNR: power within one bin of the peak and of its first harmonic over the
    rest of the band (de Haan and Jeanne 2013)."""
    f, sxx, syy, sxy = _welch(face, neck, fs)
    band = (f >= BAND_HZ[0]) & (f <= BAND_HZ[1])
    df = f[1] - f[0]
    f0 = f[band][np.argmax(sxx[band])]
    near = (np.abs(f - f0) <= df * 1.01)
    signal = band & (near | (np.abs(f - 2 * f0) <= df * 1.01))
    rest = float(sxx[band & ~signal].sum())
    snr = 10 * np.log10(float(sxx[signal].sum()) / rest) if rest > 0 else np.inf
    with np.errstate(invalid="ignore", divide="ignore"):
        msc = np.abs(sxy[near]) ** 2 / (sxx[near] * syy[near])
    msc = msc[np.isfinite(msc)]
    return float(snr), float(msc.mean()) if len(msc) else 0.0
