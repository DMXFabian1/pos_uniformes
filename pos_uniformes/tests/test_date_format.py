from __future__ import annotations

import unittest
from datetime import date, datetime, timezone, timedelta

from pos_uniformes.utils.date_format import format_display_date, format_display_datetime

CDT = timezone(timedelta(hours=-5))  # Mexico City en verano (mayo)


class FormatDisplayDatetimeTests(unittest.TestCase):
    def test_naive_datetime_formats_as_is(self) -> None:
        dt = datetime(2026, 5, 16, 14, 30)
        self.assertEqual(format_display_datetime(dt), "16/05/2026 14:30")

    def test_none_returns_empty_string(self) -> None:
        self.assertEqual(format_display_datetime(None), "")

    def test_none_returns_custom_empty(self) -> None:
        self.assertEqual(format_display_datetime(None, empty="—"), "—")

    def test_utc_datetime_converts_to_local_before_display(self) -> None:
        # 19:00 UTC == 14:00 CDT (UTC-5) — el ticket debe mostrar 14:00, no 19:00
        dt_utc = datetime(2026, 5, 16, 19, 0, tzinfo=timezone.utc)
        result = format_display_datetime(dt_utc)
        # No podemos saber la TZ del sistema en el entorno de test,
        # pero sí podemos verificar que NO muestra la hora UTC cruda
        # cuando el sistema está en una TZ distinta a UTC.
        # Lo que sí podemos garantizar: el resultado corresponde al local de dt_utc.
        expected_local = dt_utc.astimezone()
        self.assertEqual(result, expected_local.strftime("%d/%m/%Y %H:%M"))

    def test_aware_datetime_with_explicit_offset(self) -> None:
        dt_cdt = datetime(2026, 5, 16, 14, 30, tzinfo=CDT)
        result = format_display_datetime(dt_cdt)
        expected = dt_cdt.astimezone().strftime("%d/%m/%Y %H:%M")
        self.assertEqual(result, expected)


class FormatDisplayDateTests(unittest.TestCase):
    def test_date_object(self) -> None:
        self.assertEqual(format_display_date(date(2026, 5, 16)), "16/05/2026")

    def test_naive_datetime_uses_its_date(self) -> None:
        dt = datetime(2026, 5, 16, 23, 30)
        self.assertEqual(format_display_date(dt), "16/05/2026")

    def test_utc_datetime_near_midnight_uses_local_date(self) -> None:
        # 04:00 UTC del 17 == 23:00 CDT del 16 — fecha local es el 16, no el 17
        dt_utc = datetime(2026, 5, 17, 4, 0, tzinfo=timezone.utc)
        result = format_display_date(dt_utc)
        expected_local_date = dt_utc.astimezone().date()
        self.assertEqual(result, expected_local_date.strftime("%d/%m/%Y"))

    def test_none_returns_empty(self) -> None:
        self.assertEqual(format_display_date(None), "")
