"""Unit tests for nutritional_patients_service helper functions."""

from datetime import datetime, timezone

import pytest

from services.nutritional.nutritional_active_patients_service import (
    _calculate_age,
    _calculate_days,
    _calculate_imc,
)

@pytest.mark.parametrize(
    "birthdate, now, expected",
    [
        # Normal case: birthday already passed this year
        (datetime(1959, 3, 15), datetime(2026, 4, 10, tzinfo=timezone.utc), 67),
        # Birthday has NOT happened yet this year
        (datetime(1990, 12, 25), datetime(2026, 4, 10, tzinfo=timezone.utc), 35),
        # Birthday is today
        (datetime(2000, 4, 10), datetime(2026, 4, 10, tzinfo=timezone.utc), 26),
        # Newborn (same year)
        (datetime(2026, 1, 1), datetime(2026, 4, 10, tzinfo=timezone.utc), 0),
        # None birthdate
        (None, datetime(2026, 4, 10, tzinfo=timezone.utc), None),
    ],
)
def test_calculate_age(birthdate, now, expected):
    """_calculate_age retorna idade em anos completos"""
    assert _calculate_age(birthdate, now) == expected


@pytest.mark.parametrize(
    "admission_date, now, expected",
    [
        # 14 days ago
        (datetime(2026, 3, 27), datetime(2026, 4, 10, tzinfo=timezone.utc), 14),
        # Admitted today
        (datetime(2026, 4, 10), datetime(2026, 4, 10, tzinfo=timezone.utc), 0),
        # 1 day ago
        (datetime(2026, 4, 9), datetime(2026, 4, 10, tzinfo=timezone.utc), 1),
        # None
        (None, datetime(2026, 4, 10, tzinfo=timezone.utc), None),
    ],
)
def test_calculate_days(admission_date, now, expected):
    """_calculate_days retorna dias de internação"""
    assert _calculate_days(admission_date, now) == expected


@pytest.mark.parametrize(
    "peso, altura, expected",
    [
        # Normal: 58kg, 183cm → 58 / (1.83²) ≈ 17.3
        (58.0, 183.0, 17.3),
        # Normal: 65kg, 160cm → 65 / (1.60²) ≈ 25.4
        (65.0, 160.0, 25.4),
        # Normal: 80kg, 175cm → 80 / (1.75²) ≈ 26.1
        (80.0, 175.0, 26.1),
        # Missing peso
        (None, 183.0, None),
        # Missing altura
        (58.0, None, None),
        # Both missing
        (None, None, None),
        # Zero altura (edge case)
        (58.0, 0, None),
    ],
)
def test_calculate_imc(peso, altura, expected):
    """_calculate_imc calcula IMC corretamente (peso kg, altura cm)"""
    result = _calculate_imc(peso, altura)
    if expected is None:
        assert result is None
    else:
        assert result == expected

