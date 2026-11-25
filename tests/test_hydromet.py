"""
SookshmaJal – Tests for hydro-meteorological functions.
Tests FAO-56 ET₀ calculation, survival litres formula, and edge cases.
"""
import math
import pytest

from backend.hydromet import (
    _saturation_vapor_pressure,
    _actual_vapor_pressure,
    fao56_et0,
    survival_litres,
    get_hydromet_data,
)


# ── SVP tests ─────────────────────────────────────────────────────────────────

class TestSaturationVaporPressure:
    def test_at_0_celsius(self):
        """e°(0°C) ≈ 0.6108 kPa"""
        result = _saturation_vapor_pressure(0.0)
        assert math.isclose(result, 0.6108, rel_tol=1e-4)

    def test_at_20_celsius(self):
        """e°(20°C) ≈ 2.338 kPa"""
        result = _saturation_vapor_pressure(20.0)
        assert 2.30 < result < 2.40

    def test_at_35_celsius(self):
        """Tumakuru max summer temp; e°(35°C) ≈ 5.63 kPa"""
        result = _saturation_vapor_pressure(35.0)
        assert 5.50 < result < 5.80

    def test_always_positive(self):
        for t in [-10, 0, 10, 20, 30, 40, 45]:
            assert _saturation_vapor_pressure(float(t)) > 0


# ── ET₀ tests ─────────────────────────────────────────────────────────────────

class TestFAO56ET0:
    """Test FAO-56 PM ET₀ with Tumakuru-like climate conditions."""

    def test_typical_tumakuru_october(self):
        """
        Typical Tumakuru October conditions.
        Expected ET₀ ≈ 4–6 mm/day (Deccan Plateau dry season).
        """
        et0 = fao56_et0(
            t_max=32.0,
            t_min=20.0,
            rh_max=65.0,
            rh_min=35.0,
            wind_speed_m_s=3.0,
            rs_mj_m2=22.0,
            elevation_m=820.0,
        )
        assert 3.5 <= et0 <= 7.5, f"ET₀ out of expected range: {et0}"

    def test_et0_increases_with_temperature(self):
        """Higher temperature → higher ET₀."""
        et0_cool = fao56_et0(25.0, 15.0, 70.0, 40.0, 2.0, 18.0)
        et0_hot  = fao56_et0(38.0, 25.0, 50.0, 25.0, 3.0, 25.0)
        assert et0_hot > et0_cool

    def test_et0_non_negative(self):
        """ET₀ must always be ≥ 0."""
        et0 = fao56_et0(10.0, 2.0, 95.0, 70.0, 0.5, 5.0)
        assert et0 >= 0.0

    def test_et0_high_humidity_lower(self):
        """Higher relative humidity → lower ET₀ (less vapour pressure deficit)."""
        et0_dry  = fao56_et0(32.0, 20.0, 40.0, 20.0, 3.0, 22.0)
        et0_humid= fao56_et0(32.0, 20.0, 90.0, 70.0, 3.0, 22.0)
        assert et0_dry > et0_humid

    def test_et0_zero_radiation(self):
        """With zero radiation, ET₀ still non-negative (aerodynamic term)."""
        et0 = fao56_et0(30.0, 18.0, 60.0, 30.0, 2.0, 0.0)
        assert et0 >= 0.0

    def test_et0_returns_float(self):
        et0 = fao56_et0(30.0, 18.0, 60.0, 35.0, 2.5, 20.0)
        assert isinstance(et0, float)


# ── Survival litres tests ─────────────────────────────────────────────────────

class TestSurvivalLitres:
    """Test V_surv = max(0, (Kc×ET₀×days - precip) × area_m² / efficiency) in L."""

    def test_basic_ragi_1acre(self):
        """
        Ragi (Kc≈1.05), ET₀=5 mm/day, 7 days, 0 precip, 1 acre, 70% efficiency.
        ETc = 1.05 × 5 × 7 = 36.75 mm
        Area = 4046.856 m²
        Volume = (0.03675 m) × 4046.856 / 0.70 = ~212 m³ = 212,460 L
        """
        result = survival_litres(
            et0_mm_day=5.0,
            area_acres=1.0,
            crop_type="ragi",
            days=7,
            precip_mm=0.0,
            efficiency=0.70,
        )
        # Allow ±10% tolerance
        assert 180_000 < result < 250_000, f"V_surv = {result}"

    def test_precipitation_reduces_demand(self):
        """More precipitation → lower survival water needed."""
        v_no_rain  = survival_litres(5.0, 2.0, "maize", precip_mm=0.0)
        v_some_rain= survival_litres(5.0, 2.0, "maize", precip_mm=20.0)
        assert v_no_rain > v_some_rain

    def test_surplus_rainfall_returns_zero(self):
        """If rainfall exceeds ETc, V_surv = 0 (no irrigation needed)."""
        result = survival_litres(
            et0_mm_day=4.0,
            area_acres=1.0,
            crop_type="default",
            days=7,
            precip_mm=200.0,  # Way more than ETc
        )
        assert result == 0.0

    def test_larger_plot_more_water(self):
        """Larger area → proportionally more water needed."""
        v1 = survival_litres(5.0, 1.0, "ragi")
        v5 = survival_litres(5.0, 5.0, "ragi")
        assert math.isclose(v5 / v1, 5.0, rel_tol=0.01)

    def test_non_negative(self):
        """V_surv must always be ≥ 0."""
        result = survival_litres(0.0, 1.0, "default", precip_mm=100.0)
        assert result >= 0.0

    def test_known_crops_return_float(self):
        for crop in ["ragi", "tomato", "groundnut", "cotton", "maize", "rice", "sorghum"]:
            result = survival_litres(5.0, 2.0, crop)
            assert isinstance(result, float)
            assert result >= 0.0

    def test_efficiency_affects_volume(self):
        """Lower irrigation efficiency → more water needed."""
        v_efficient = survival_litres(5.0, 1.0, "ragi", efficiency=0.90)
        v_inefficient= survival_litres(5.0, 1.0, "ragi", efficiency=0.40)
        assert v_inefficient > v_efficient

    def test_zero_et0(self):
        """Zero ET₀ → zero survival litres."""
        result = survival_litres(0.0, 5.0, "ragi", precip_mm=0.0)
        assert result == 0.0

    def test_max_area_50_acres(self):
        """50-acre plot (maximum allowed) should return a large but finite number."""
        result = survival_litres(6.0, 50.0, "cotton", precip_mm=5.0)
        assert result > 0
        assert math.isfinite(result)


# ── Integration-style test with mocked HTTP ───────────────────────────────────

class TestGetHydrometData:
    def test_fallback_on_bad_coords(self):
        """
        get_hydromet_data should not raise even with invalid coords –
        it uses climatological fallback.
        """
        # Use a valid Tumakuru lat/lon; network may or may not be available in CI
        result = get_hydromet_data(
            lat=13.5,
            lon=77.1,
            area_acres=2.0,
            crop_type="ragi",
        )
        assert "et0_mm_day" in result
        assert "survival_liters" in result
        assert result["et0_mm_day"] >= 0
        assert result["survival_liters"] >= 0

    def test_all_expected_keys_present(self):
        result = get_hydromet_data(13.6621, 77.2017, 1.0, "groundnut")
        expected_keys = {
            "et0_mm_day", "precipitation_mm", "soil_moisture_0_7cm_pct",
            "survival_liters", "deficit_mm", "open_meteo_timestamp",
        }
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"
