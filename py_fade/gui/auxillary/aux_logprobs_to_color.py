"""Utilities for mapping token logprob values to color codes."""

import numpy as np
from PyQt6.QtGui import QColor


def hsv_to_rgb(h, s, v) -> tuple[float, float, float]:  # type: ignore
    """Convert HSV (0–1 floats) to RGB (0–1 floats)."""
    i = int(h * 6.0)
    f = (h * 6.0) - i
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    i %= 6
    if i == 0:
        return v, t, p
    if i == 1:
        return q, v, p
    if i == 2:
        return p, v, t
    if i == 3:
        return p, q, v
    if i == 4:
        return t, p, v
    if i == 5:
        return v, p, q
    raise ValueError("h must be in [0, 1]")  # pragma: no cover - should not happen


def logprob_to_qcolor(
    logprob: float, min_lp: float = -20.0, max_lp: float = -0.2, nonlinear: str = "sqrt"
) -> QColor:
    """
    Map a logprob value to a green-yellow-red QColor for heatmaps in PyQt6.

    Parameters
    ----------
    logprob : float
        Log probability value.
    min_lp : float
        Minimum logprob mapped to red (default -20).
    max_lp : float
        Maximum logprob mapped to green (default -0.2).
    nonlinear : str
        Nonlinear scaling: 'linear', 'sqrt', or 'sigmoid'.

    Returns
    -------
    QColor
        A QColor object representing the mapped color.
    """
    # Normalize to [0, 1]
    x = (logprob - min_lp) / (max_lp - min_lp)
    x = max(0.0, min(1.0, x))  # clamp

    # Nonlinear transform
    if nonlinear == "sqrt":
        y = np.sqrt(x)
    elif nonlinear == "sigmoid":
        k = 10.0
        y = 1.0 / (1.0 + np.exp(-k * (x - 0.5)))
    else:
        y = x

    # Map y (0=red, 0.5=yellow, 1=green) using HSV
    # Hue 0.0 = red, 0.33 = green
    hue = y * 0.33
    sat = 1.0
    val = 1.0

    # Convert HSV → RGB
    r, g, b = [int(255 * c) for c in hsv_to_rgb(hue, sat, val)]
    return QColor(r, g, b)
