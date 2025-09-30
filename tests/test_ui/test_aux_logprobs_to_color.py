"""
Tests for aux_logprobs_to_color module.

Tests the logprob_to_qcolor function with the new improved color spectrum
from Dark Green → Orange → Red → Purple.
"""

from PyQt6.QtGui import QColor

from py_fade.gui.auxillary.aux_logprobs_to_color import logprob_to_qcolor


class TestLogprobToQColor:
    """
    Test the logprob_to_qcolor function with the new color spectrum.
    
    The new spectrum should go from Dark Green to Orange to Red to Purple
    with specific thresholds and hex values as specified in the requirements.
    """

    def test_exact_threshold_colors(self):
        """
        Test that exact threshold logprob values map to their specified hex colors.
        
        Tests the 18 specified logprob thresholds with their exact hex color mappings
        from the requirements.
        """
        # Expected mappings from requirements
        expected_mappings = [
            (-0.05, "#006400"),  # Dark green
            (-0.1, "#337100"),  # Slight orange tint, mostly green
            (-0.22, "#4E7700"),
            (-0.35, "#697E00"),
            (-1.0, "#848500"),
            (-2.3, "#9C8B00"),
            (-4.6, "#EDA000"),
            (-10.0, "#FF6C00"),
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

        for logprob, expected_hex in expected_mappings:
            color = logprob_to_qcolor(logprob)
            actual_hex = f"#{color.red():02X}{color.green():02X}{color.blue():02X}"

            # Allow some tolerance for color conversion rounding
            expected_color = QColor(expected_hex)
            assert abs(color.red() - expected_color.red()) <= 2, \
                f"logprob {logprob}: expected {expected_hex}, got {actual_hex} (red channel mismatch)"
            assert abs(color.green() - expected_color.green()) <= 2, \
                f"logprob {logprob}: expected {expected_hex}, got {actual_hex} (green channel mismatch)"
            assert abs(color.blue() - expected_color.blue()) <= 2, \
                f"logprob {logprob}: expected {expected_hex}, got {actual_hex} (blue channel mismatch)"

    def test_color_progression_dark_green_to_orange(self):
        """
        Test that colors progress appropriately from dark green to orange in the upper probability range.
        
        Tests the transition from p=0.95 (logprob=-0.05) to p=0.01 (logprob=-4.6).
        The progression follows the specified hex values which prioritize visual distinction
        over strict mathematical monotonicity.
        """
        # Test progression from high probability (dark green) to medium probability (orange)
        logprob_progression = [-0.05, -0.1, -0.22, -0.35, -1.0, -2.3, -4.6]
        colors = [logprob_to_qcolor(lp) for lp in logprob_progression]

        # Verify we have distinct colors across the progression
        unique_colors = set((c.red(), c.green(), c.blue()) for c in colors)
        assert len(unique_colors) == len(colors), "All colors in progression should be distinct"

        # Verify the overall trend toward orange/red: red component should generally increase
        # (allowing for some local variations due to the specific color design)
        first_red = colors[0].red()
        last_red = colors[-1].red()
        assert last_red > first_red + 100, \
            f"Red component should increase significantly from dark green to orange: {first_red} -> {last_red}"

        # Verify that we end up with an orange-like color (high red, moderate green)
        final_color = colors[-1]
        assert final_color.red() > 200, "Final color should have high red component (orange)"
        assert final_color.green() > 100, "Final color should have moderate green component (orange)"
        assert final_color.blue() < 50, "Final color should have low blue component (orange)"

    def test_color_progression_orange_to_red_to_purple(self):
        """
        Test that colors progress smoothly from orange to red to purple in the lower probability range.
        
        Tests the transition from medium probability (orange) to very low probability (purple).
        """
        # Test progression from orange to red to purple
        logprob_progression = [-4.6, -10.0, -16.0, -20.0, -25.0, -29.0]
        colors = [logprob_to_qcolor(lp) for lp in logprob_progression]

        # Check that we have distinct colors across the spectrum
        unique_colors = set((c.red(), c.green(), c.blue()) for c in colors)
        assert len(unique_colors) >= 5, "Should have diverse colors across the orange-red-purple spectrum"

        # Verify the final color (logprob -29.0) has purple characteristics
        final_color = colors[-1]
        assert final_color.red() > 100, "Final purple color should have significant red component"
        assert final_color.blue() > 100, "Final purple color should have significant blue component"

    def test_extreme_values_clamping(self):
        """
        Test that extreme logprob values are clamped to the appropriate range boundaries.
        
        Very high logprobs should map to dark green, very low logprobs should map to purple.
        """
        # Test extremely high probability (should clamp to dark green)
        very_high_logprob = 0.0  # Perfect probability
        high_color = logprob_to_qcolor(very_high_logprob)
        expected_high_color = logprob_to_qcolor(-0.05)  # Should be same as our highest threshold

        assert high_color.red() == expected_high_color.red()
        assert high_color.green() == expected_high_color.green()
        assert high_color.blue() == expected_high_color.blue()

        # Test extremely low probability (should clamp to purple)
        very_low_logprob = -100.0
        low_color = logprob_to_qcolor(very_low_logprob)
        expected_low_color = logprob_to_qcolor(-29.0)  # Should be same as our lowest threshold

        assert low_color.red() == expected_low_color.red()
        assert low_color.green() == expected_low_color.green()
        assert low_color.blue() == expected_low_color.blue()

    def test_intermediate_values_interpolation(self):
        """
        Test that intermediate logprob values are properly interpolated between thresholds.
        
        Values between specified thresholds should have colors that are interpolated.
        """
        # Test a value between -0.1 and -0.22
        intermediate_logprob = -0.16
        intermediate_color = logprob_to_qcolor(intermediate_logprob)

        color_before = logprob_to_qcolor(-0.1)
        color_after = logprob_to_qcolor(-0.22)

        # Intermediate color components should be between the boundary colors
        assert min(color_before.red(), color_after.red()) <= intermediate_color.red() <= max(color_before.red(), color_after.red())
        assert min(color_before.green(), color_after.green()) <= intermediate_color.green() <= max(
            color_before.green(), color_after.green())
        assert min(color_before.blue(), color_after.blue()) <= intermediate_color.blue() <= max(
            color_before.blue(), color_after.blue())

    def test_backwards_compatibility_function_signature(self):
        """
        Test that the function maintains backwards compatibility with existing call signatures.
        
        The existing code uses the function with just the logprob parameter,
        so we need to ensure this still works.
        """
        # Test with just logprob parameter (existing usage pattern)
        result = logprob_to_qcolor(-1.0)
        assert isinstance(result, QColor)

        # Test that old parameters are still accepted for backwards compatibility
        # (even if they might not be used in the new implementation)
        result_with_old_params = logprob_to_qcolor(-1.0, min_lp=-20.0, max_lp=-0.2, nonlinear="sqrt")
        assert isinstance(result_with_old_params, QColor)

    def test_distinct_upper_probability_colors(self):
        """
        Test that upper probability values have distinct colors for visual differentiation.
        
        This addresses the requirement to see distinctions between p=0.95 vs p=0.9
        and in the tail between -20 vs -25 or -10 vs -15.
        """
        # Test distinction in upper probability range
        p95_color = logprob_to_qcolor(-0.05)  # p=0.95
        p90_color = logprob_to_qcolor(-0.105)  # p≈0.9

        # Colors should be visually distinct
        color_distance = abs(p95_color.red() - p90_color.red()) + \
                        abs(p95_color.green() - p90_color.green()) + \
                        abs(p95_color.blue() - p90_color.blue())
        assert color_distance > 10, "p=0.95 and p=0.9 should have visually distinct colors"

        # Test distinction in tail
        tail_20_color = logprob_to_qcolor(-20.0)
        tail_25_color = logprob_to_qcolor(-25.0)

        tail_distance = abs(tail_20_color.red() - tail_25_color.red()) + \
                       abs(tail_20_color.green() - tail_25_color.green()) + \
                       abs(tail_20_color.blue() - tail_25_color.blue())
        assert tail_distance > 10, "logprob -20 and -25 should have visually distinct colors"

    def test_return_type_is_qcolor(self):
        """
        Test that the function always returns a QColor object.
        
        Ensures type safety for GUI usage.
        """
        test_logprobs = [-0.05, -1.0, -10.0, -29.0]
        for logprob in test_logprobs:
            result = logprob_to_qcolor(logprob)
            assert isinstance(result, QColor), f"Result for logprob {logprob} should be QColor"
            assert result.isValid(), f"QColor for logprob {logprob} should be valid"
