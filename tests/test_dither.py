"""Tests for Floyd-Steinberg dithering."""

import numpy as np
import pytest

from ascii_maker.core.dither import floyd_steinberg


class TestFloydSteinberg:
    def test_binary_output_range(self):
        """Output should be in [0, 1]."""
        gray = np.random.rand(10, 10)
        result = floyd_steinberg(gray, levels=2)
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_binary_only_two_values(self):
        """With levels=2, output should be only 0.0 and 1.0."""
        gray = np.random.rand(10, 10)
        result = floyd_steinberg(gray, levels=2)
        unique = np.unique(np.round(result, 6))
        assert len(unique) <= 2
        for v in unique:
            assert v == pytest.approx(0.0, abs=0.01) or v == pytest.approx(
                1.0, abs=0.01
            )

    def test_all_black_stays_black(self):
        gray = np.zeros((5, 5))
        result = floyd_steinberg(gray, levels=2)
        assert np.allclose(result, 0.0)

    def test_all_white_stays_white(self):
        gray = np.ones((5, 5))
        result = floyd_steinberg(gray, levels=2)
        assert np.allclose(result, 1.0)

    def test_multi_level(self):
        """With levels=4, output should have up to 4 distinct values."""
        gray = np.linspace(0, 1, 100).reshape(10, 10)
        result = floyd_steinberg(gray, levels=4)
        unique = np.unique(np.round(result, 2))
        assert len(unique) <= 4

    def test_preserves_shape(self):
        gray = np.random.rand(15, 20)
        result = floyd_steinberg(gray, levels=2)
        assert result.shape == (15, 20)

    def test_mean_preservation(self):
        """Dithering should roughly preserve the mean luminance."""
        gray = np.full((20, 20), 0.5)
        result = floyd_steinberg(gray, levels=2)
        # Mean should be approximately 0.5 (within tolerance for error diffusion)
        assert abs(result.mean() - 0.5) < 0.15
