"""Utilities for mapping token logprob values to color codes."""

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


def logprob_to_qcolor(logprob: float, min_lp: float = -20.0, max_lp: float = -0.2, nonlinear: str = "sqrt") -> QColor:
    """
    Map a logprob value to a color using improved Dark Green → Orange → Red → Purple spectrum.

    The new color scheme provides better visual distinction across probability ranges,
    with specific thresholds for upper probabilities (p=0.95 vs p=0.9) and tail
    distinctions (-20 vs -25, -10 vs -15).

    The color progression goes:
    - Upper probabilities (p ≥ 0.95, logprob ≥ -0.05): Dark Green
    - High probabilities (p ≥ 0.9, logprob ≥ -0.1): Green with slight orange tint
    - Medium probabilities: Green to Orange transition
    - Low probabilities: Orange to Red transition
    - Very low probabilities: Red to Purple transition

    Parameters
    ----------
    logprob : float
        Log probability value to map to color.
    min_lp : float
        Legacy parameter maintained for backwards compatibility (not used in new implementation).
    max_lp : float
        Legacy parameter maintained for backwards compatibility (not used in new implementation).
    nonlinear : str
        Legacy parameter maintained for backwards compatibility (not used in new implementation).

    Returns
    -------
    QColor
        A QColor object representing the mapped color in the improved spectrum.
    """
    # Legacy parameters are intentionally unused in the new implementation
    # They are kept for backwards compatibility with existing code
    _ = min_lp, max_lp, nonlinear

    # Define the improved color mapping with specific logprob thresholds and hex colors
    # These are the 18 specified thresholds from the requirements
    color_thresholds = [
        (-0.05, "#006400"),  # Dark green (p=0.95)
        (-0.1, "#337100"),  # Slight orange tint, mostly green (p<0.9)
        (-0.22, "#4E7700"),  # (p<0.8)
        (-0.35, "#697E00"),  # (p<0.7)
        (-1.0, "#848500"),  # (p<0.35)
        (-2.3, "#9C8B00"),  # (p<0.1)
        (-4.6, "#EDA000"),  # (p<0.01)
        (-10.0, "#FF6C00"),  # (p<0.000045)
        (-16.0, "#FF3800"),
        (-18.0, "#FF0500"),
        (-20.0, "#E80016"),
        (-22.0, "#CD0031"),
        (-24.0, "#C1003D"),
        (-25.0, "#B4004B"),
        (-26.0, "#A60058"),
        (-27.0, "#990066"),
        (-28.0, "#8B0073"),
        (-29.0, "#800080"),  # Purple
    ]

    # Sort thresholds by logprob in descending order for proper interpolation
    sorted_thresholds = sorted(color_thresholds, key=lambda x: x[0], reverse=True)

    # Handle extreme values by clamping to the boundary colors
    if logprob >= sorted_thresholds[0][0]:
        # Use the highest threshold color (dark green)
        hex_color = sorted_thresholds[0][1]
        return QColor(hex_color)

    if logprob <= sorted_thresholds[-1][0]:
        # Use the lowest threshold color (purple)
        hex_color = sorted_thresholds[-1][1]
        return QColor(hex_color)

    # Find the two adjacent thresholds for linear interpolation
    for i in range(len(sorted_thresholds) - 1):
        logprob_upper, hex_upper = sorted_thresholds[i]
        logprob_lower, hex_lower = sorted_thresholds[i + 1]

        if logprob_lower <= logprob <= logprob_upper:
            # Perform linear interpolation between the two colors
            # Calculate interpolation factor (0.0 = lower color, 1.0 = upper color)
            if logprob_upper == logprob_lower:
                # Handle edge case where thresholds are identical
                t = 0.0
            else:
                t = (logprob - logprob_lower) / (logprob_upper - logprob_lower)

            # Parse hex colors to RGB components
            color_upper = QColor(hex_upper)
            color_lower = QColor(hex_lower)

            # Interpolate each RGB component
            r = int(color_lower.red() + t * (color_upper.red() - color_lower.red()))
            g = int(color_lower.green() + t * (color_upper.green() - color_lower.green()))
            b = int(color_lower.blue() + t * (color_upper.blue() - color_lower.blue()))

            # Ensure RGB values are in valid range [0, 255]
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))

            return QColor(r, g, b)

    # Fallback (should not reach here with proper threshold coverage)
    return QColor("#FF0000")  # Red as fallback
