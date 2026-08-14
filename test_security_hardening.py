"""Offline regression tests for ingestion and expression hardening."""

from __future__ import annotations

import io
import unittest
from unittest import mock

import numpy as np
import pandas as pd

import data_cleaner as cleaner
import data_loader as loader
import eviews_emulator as eviews


def _named_buffer(payload: bytes, name: str) -> io.BytesIO:
    buffer = io.BytesIO(payload)
    buffer.name = name
    return buffer


def _history(start: str, end: str, *, offset: float = 0.0) -> pd.DataFrame:
    dates = pd.bdate_range(start, end)
    return pd.DataFrame(
        {
            "time": dates,
            "close": np.arange(len(dates), dtype=float) + 10.0 + offset,
            "volume": np.full(len(dates), 1_000),
        }
    )


class _FakeQuote:
    payloads = {}
    intraday_payloads = {}
    history_calls = []
    intraday_calls = []

    def __init__(self, symbol: str, source: str):
        self.symbol = symbol
        self.source = source

    def history(self, start: str, end: str):
        self.history_calls.append((self.source, self.symbol))
        source_key = (self.source, self.symbol)
        payload = (
            self.payloads[source_key]
            if source_key in self.payloads
            else self.payloads[self.symbol]
        )
        if isinstance(payload, Exception):
            raise payload
        return payload.copy()

    def intraday(self, page_size: int):
        self.intraday_calls.append((self.source, self.symbol, page_size))
        source_key = (self.source, self.symbol)
        payload = (
            self.intraday_payloads[source_key]
            if source_key in self.intraday_payloads
            else self.intraday_payloads[self.symbol]
        )
        if isinstance(payload, Exception):
            raise payload
        return payload.copy().tail(page_size)


class MarketDataHardeningTests(unittest.TestCase):
    def setUp(self):
        _FakeQuote.payloads = {}
        _FakeQuote.intraday_payloads = {}
        _FakeQuote.history_calls = []
        _FakeQuote.intraday_calls = []
        loader._reset_source_circuit_breakers()

    def tearDown(self):
        loader._reset_source_circuit_breakers()

    def test_filters_range_sorts_and_deduplicates(self):
        start, end = "2024-01-02", "2024-01-12"
        base = _history(start, end)
        duplicate = base.iloc[[3]].copy()
        duplicate["close"] = 123.0
        outside = pd.DataFrame(
            {
                "time": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-15")],
                "close": [8.0, 30.0],
                "volume": [1_000, 1_000],
            }
        )
        raw = pd.concat([base.iloc[::-1], duplicate, outside], ignore_index=True)
        _FakeQuote.payloads["AAA"] = raw
        with mock.patch.object(loader, "Quote", _FakeQuote):
            result = loader.fetch_data_result(["aaa"], start, end)

        self.assertTrue(result.ok, result.report.to_dict())
        self.assertEqual(list(result.data.columns), ["AAA"])
        self.assertTrue(result.data.index.is_monotonic_increasing)
        self.assertTrue(result.data.index.is_unique)
        self.assertEqual(result.data.index.min(), pd.Timestamp(start))
        self.assertEqual(result.data.index.max(), pd.Timestamp(end))
        self.assertEqual(float(result.data.loc[pd.Timestamp("2024-01-05"), "AAA"]), 123.0)
        self.assertIn("fetch_report", result.data.attrs)
        self.assertIn(
            "DUPLICATE_TIMESTAMPS_DROPPED",
            [issue.code for issue in result.report.warnings],
        )

    def test_provider_failure_never_returns_partial_portfolio(self):
        start, end = "2024-02-01", "2024-02-15"
        _FakeQuote.payloads = {
            "AAA": _history(start, end),
            "BBB": RuntimeError("provider unavailable"),
        }
        with mock.patch.object(loader, "Quote", _FakeQuote):
            result = loader.fetch_data_result(["AAA", "BBB"], start, end)
            with self.assertRaises(loader.DataFetchError):
                loader.fetch_data(["AAA", "BBB"], start, end)

        self.assertFalse(result.ok)
        self.assertTrue(result.data.empty)
        codes = {issue.code for issue in result.report.errors}
        self.assertTrue({"PROVIDER_ERROR", "INCOMPLETE_PORTFOLIO"}.issubset(codes))

    def test_data_source_fallback_returns_complete_portfolio(self):
        start, end = "2024-02-01", "2024-02-15"
        _FakeQuote.payloads = {
            ("KBS", "AAA"): RuntimeError("kbs unavailable"),
            ("KBS", "BBB"): RuntimeError("kbs unavailable"),
            ("VCI", "AAA"): _history(start, end),
            ("VCI", "BBB"): _history(start, end, offset=50),
        }
        with mock.patch.object(loader, "Quote", _FakeQuote):
            result = loader.fetch_data_result(["AAA", "BBB"], start, end)

        self.assertTrue(result.ok, result.report.to_dict())
        self.assertEqual(result.report.source, "VCI")
        self.assertEqual(list(result.data.columns), ["AAA", "BBB"])
        self.assertIn(
            "DATA_SOURCE_FALLBACK_USED",
            [issue.code for issue in result.report.warnings],
        )

    def test_history_provider_wide_failure_opens_and_expires_cooldown(self):
        start, end = "2024-02-01", "2024-02-15"
        clock = [100.0]
        _FakeQuote.payloads = {
            ("KBS", "AAA"): RuntimeError("kbs blocked"),
            ("KBS", "BBB"): RuntimeError("kbs blocked"),
            ("VCI", "AAA"): _history(start, end),
            ("VCI", "BBB"): _history(start, end, offset=50),
        }
        with (
            mock.patch.object(loader, "Quote", _FakeQuote),
            mock.patch.object(loader, "monotonic", side_effect=lambda: clock[0]),
        ):
            first = loader.fetch_data_result(
                ["AAA", "BBB"], start, end, source=["KBS", "VCI"]
            )
            first_kbs_calls = [c for c in _FakeQuote.history_calls if c[0] == "KBS"]

            clock[0] = 101.0
            second = loader.fetch_data_result(
                ["AAA", "BBB"], start, end, source=["KBS", "VCI"]
            )
            second_kbs_calls = [c for c in _FakeQuote.history_calls if c[0] == "KBS"]

            clock[0] = 401.0
            _FakeQuote.payloads[("KBS", "AAA")] = _history(start, end)
            _FakeQuote.payloads[("KBS", "BBB")] = _history(start, end, offset=50)
            third = loader.fetch_data_result(
                ["AAA", "BBB"], start, end, source=["KBS", "VCI"]
            )

        self.assertTrue(first.ok, first.report.to_dict())
        self.assertEqual(len(first_kbs_calls), 2)
        self.assertTrue(second.ok, second.report.to_dict())
        self.assertEqual(second_kbs_calls, first_kbs_calls)
        cooldowns = [i for i in second.report.warnings if i.code == "SOURCE_COOLDOWN"]
        self.assertEqual(len(cooldowns), 1)
        self.assertEqual(cooldowns[0].details["source"], "KBS")
        self.assertEqual(cooldowns[0].details["operation"], "history")
        self.assertEqual(cooldowns[0].details["remaining_seconds"], 299.0)
        self.assertTrue(third.ok, third.report.to_dict())
        self.assertEqual(third.report.source, "KBS")
        self.assertEqual(
            len([c for c in _FakeQuote.history_calls if c[0] == "KBS"]), 4
        )

    def test_history_partial_provider_error_never_opens_cooldown(self):
        start, end = "2024-02-01", "2024-02-15"
        clock = [100.0]
        _FakeQuote.payloads = {
            ("KBS", "AAA"): RuntimeError("one symbol failed"),
            ("KBS", "BBB"): _history(start, end),
            ("VCI", "AAA"): _history(start, end),
            ("VCI", "BBB"): _history(start, end, offset=50),
        }
        with (
            mock.patch.object(loader, "Quote", _FakeQuote),
            mock.patch.object(loader, "monotonic", side_effect=lambda: clock[0]),
        ):
            first = loader.fetch_data_result(
                ["AAA", "BBB"], start, end, source=["KBS", "VCI"]
            )
            clock[0] = 101.0
            second = loader.fetch_data_result(
                ["AAA", "BBB"], start, end, source=["KBS", "VCI"]
            )

        self.assertTrue(first.ok, first.report.to_dict())
        self.assertTrue(second.ok, second.report.to_dict())
        self.assertEqual(
            len([c for c in _FakeQuote.history_calls if c[0] == "KBS"]), 4
        )
        self.assertNotIn(
            "SOURCE_COOLDOWN", [issue.code for issue in second.report.issues]
        )

    def test_msn_fallback_normalises_equity_but_not_index(self):
        # Simulates Streamlit Cloud where both VN brokers are IP-blocked and only
        # MSN answers. MSN quotes equities in absolute VND (~1000x), indices are
        # already on the nghìn-đồng scale.
        start, end = "2024-02-01", "2024-02-15"
        base_equity = _history(start, end)
        msn_equity = base_equity.copy()
        msn_equity["close"] = msn_equity["close"] * loader._MSN_PRICE_SCALE
        msn_index = _history(start, end, offset=1000.0)
        _FakeQuote.payloads = {
            ("KBS", "AAA"): RuntimeError("kbs blocked on cloud"),
            ("KBS", "VNINDEX"): RuntimeError("kbs blocked on cloud"),
            ("VCI", "AAA"): RuntimeError("vci blocked on cloud"),
            ("VCI", "VNINDEX"): RuntimeError("vci blocked on cloud"),
            ("MSN", "AAA"): msn_equity,
            ("MSN", "VNINDEX"): msn_index,
        }
        with mock.patch.object(loader, "Quote", _FakeQuote):
            result = loader.fetch_data_result(["AAA", "VNINDEX"], start, end)

        self.assertTrue(result.ok, result.report.to_dict())
        self.assertEqual(result.report.source, "MSN")
        # Equity rescaled back to nghìn-đồng (matches the un-scaled fixture).
        self.assertAlmostEqual(
            float(result.data["AAA"].iloc[-1]),
            float(base_equity["close"].iloc[-1]),
            places=6,
        )
        # Index must never be divided by 1000.
        self.assertGreater(float(result.data["VNINDEX"].iloc[-1]), 1000.0)

    def test_rejects_constant_and_phantom_prefix_series(self):
        start, end = "2024-03-01", "2024-04-04"
        dates = pd.bdate_range(start, end)
        constant = pd.DataFrame(
            {"time": dates, "close": 100.0, "volume": 1_000}
        )
        phantom_prices = np.r_[np.full(20, 100.0), np.arange(len(dates) - 20) + 101.0]
        phantom_volume = np.r_[np.zeros(20), np.full(len(dates) - 20, 1_000)]
        phantom = pd.DataFrame(
            {"time": dates, "close": phantom_prices, "volume": phantom_volume}
        )

        with mock.patch.object(loader, "Quote", _FakeQuote):
            _FakeQuote.payloads["AAA"] = constant
            constant_result = loader.fetch_data_result(["AAA"], start, end)
            _FakeQuote.payloads["AAA"] = phantom
            phantom_result = loader.fetch_data_result(["AAA"], start, end)

        self.assertIn("CONSTANT_SERIES", [i.code for i in constant_result.report.errors])
        self.assertIn(
            "SUSPICIOUS_CONSTANT_PREFIX",
            [i.code for i in phantom_result.report.errors],
        )

    def test_rejects_stale_series_even_with_relaxed_coverage(self):
        start, end = "2024-05-01", "2024-05-15"
        _FakeQuote.payloads["AAA"] = _history(start, "2024-05-03")
        with mock.patch.object(loader, "Quote", _FakeQuote):
            result = loader.fetch_data_result(
                ["AAA"],
                start,
                end,
                min_coverage=0.20,
                max_staleness_business_days=1,
            )
        self.assertFalse(result.ok)
        self.assertIn("STALE_SERIES", [issue.code for issue in result.report.errors])

    def test_invalid_request_is_structured(self):
        result = loader.fetch_data_result(123, "2024-01-01", "2024-01-10")
        self.assertFalse(result.ok)
        self.assertEqual(result.report.errors[0].code, "INVALID_REQUEST")

    def test_intraday_time_only_uses_vietnam_trading_date_and_reports_lag(self):
        fetched_at = pd.Timestamp("2026-08-14 10:00:30", tz="Asia/Ho_Chi_Minh")
        _FakeQuote.intraday_payloads[("KBS", "CTG")] = pd.DataFrame(
            {
                "symbol": ["CTG", "CTG"],
                "time": ["09:59:30", "10:00:00"],
                "price": [32.4, 32.45],
                "volume": [100, 200],
            }
        )
        with (
            mock.patch.object(loader, "Quote", _FakeQuote),
            mock.patch.object(loader, "vietnam_now", return_value=fetched_at),
        ):
            result = loader.fetch_intraday("ctg", page_size=500, source="KBS")

        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.symbol, "CTG")
        self.assertEqual(result.query_signature, "CTG:500")
        self.assertTrue(result.matches_query("CTG", 500))
        self.assertFalse(result.matches_query("FPT", 500))
        self.assertEqual(result.trading_date.isoformat(), "2026-08-14")
        self.assertEqual(str(result.last_tick_time.tz), "Asia/Ho_Chi_Minh")
        self.assertEqual(result.lag_seconds, 30.0)

    def test_intraday_exception_cooldown_skips_source_without_caching_data(self):
        fetched_at = pd.Timestamp("2026-08-14 10:00:30", tz="Asia/Ho_Chi_Minh")
        clock = [100.0]
        fresh_ticks = pd.DataFrame(
            {"time": ["2026-08-14 10:00:00"], "price": [32.45]}
        )
        _FakeQuote.intraday_payloads = {
            ("KBS", "CTG"): RuntimeError("kbs intraday unavailable"),
            ("VCI", "CTG"): fresh_ticks,
        }
        with (
            mock.patch.object(loader, "Quote", _FakeQuote),
            mock.patch.object(loader, "vietnam_now", return_value=fetched_at),
            mock.patch.object(loader, "monotonic", side_effect=lambda: clock[0]),
        ):
            first = loader.fetch_intraday(
                "CTG", source=["KBS", "VCI"], page_size=500
            )
            clock[0] = 101.0
            second = loader.fetch_intraday(
                "CTG", source=["KBS", "VCI"], page_size=500
            )
            clock[0] = 161.0
            _FakeQuote.intraday_payloads[("KBS", "CTG")] = fresh_ticks
            third = loader.fetch_intraday(
                "CTG", source=["KBS", "VCI"], page_size=500
            )

        self.assertTrue(first.ok, first.error)
        self.assertEqual(first.source, "VCI")
        self.assertIn("PROVIDER_ERROR", [issue.code for issue in first.issues])
        self.assertTrue(second.ok, second.error)
        self.assertEqual(second.source, "VCI")
        cooldowns = [issue for issue in second.issues if issue.code == "SOURCE_COOLDOWN"]
        self.assertEqual(len(cooldowns), 1)
        self.assertEqual(cooldowns[0].details["remaining_seconds"], 59.0)
        self.assertEqual(
            len([c for c in _FakeQuote.intraday_calls if c[0] == "KBS"]), 2
        )
        # VCI is called again on the second request: successful prices are never cached.
        self.assertEqual(
            len([c for c in _FakeQuote.intraday_calls if c[0] == "VCI"]), 2
        )
        self.assertTrue(third.ok, third.error)
        self.assertEqual(third.source, "KBS")

    def test_intraday_prefers_full_timestamp_over_time_only_column(self):
        fetched_at = pd.Timestamp("2026-08-14 10:00:30", tz="Asia/Ho_Chi_Minh")
        _FakeQuote.intraday_payloads[("KBS", "CTG")] = pd.DataFrame(
            {
                # `trading_time` appears earlier in the alias list, but only the
                # `time` column carries authoritative date provenance.
                "trading_time": ["10:00:00"],
                "time": ["2026-08-14 09:59:45"],
                "price": [32.45],
            }
        )
        with (
            mock.patch.object(loader, "Quote", _FakeQuote),
            mock.patch.object(loader, "vietnam_now", return_value=fetched_at),
        ):
            result = loader.fetch_intraday("CTG", source="KBS")

        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.last_tick_time.strftime("%Y-%m-%d %H:%M:%S"),
                         "2026-08-14 09:59:45")
        self.assertEqual(result.lag_seconds, 45.0)

    def test_intraday_provider_symbol_mismatch_fails_closed(self):
        fetched_at = pd.Timestamp("2026-08-14 10:01:00", tz="Asia/Ho_Chi_Minh")
        _FakeQuote.intraday_payloads[("KBS", "CTG")] = pd.DataFrame(
            {
                "symbol": ["FPT"],
                "time": ["2026-08-14 10:00:30"],
                "price": [109.0],
            }
        )
        with (
            mock.patch.object(loader, "Quote", _FakeQuote),
            mock.patch.object(loader, "vietnam_now", return_value=fetched_at),
        ):
            result = loader.fetch_intraday("CTG", source="KBS")

        self.assertFalse(result.ok)
        self.assertTrue(result.data.empty)
        self.assertEqual(result.symbol, "CTG")
        self.assertEqual(result.freshness, "symbol_mismatch")
        self.assertIn("FPT", result.error)
        self.assertIn("CTG", result.error)

    def test_intraday_previous_day_and_excess_lag_are_rejected(self):
        fetched_at = pd.Timestamp("2026-08-14 10:00:00", tz="Asia/Ho_Chi_Minh")
        previous_day = pd.DataFrame(
            {"time": ["2026-08-13 14:29:00"], "price": [32.4]}
        )
        delayed_today = pd.DataFrame(
            {"time": ["2026-08-14 09:30:00"], "price": [32.4]}
        )
        with (
            mock.patch.object(loader, "Quote", _FakeQuote),
            mock.patch.object(loader, "vietnam_now", return_value=fetched_at),
        ):
            _FakeQuote.intraday_payloads[("KBS", "CTG")] = previous_day
            old_result = loader.fetch_intraday("CTG", source="KBS")
            _FakeQuote.intraday_payloads[("KBS", "CTG")] = delayed_today
            lagged_result = loader.fetch_intraday("CTG", source="KBS")

        self.assertFalse(old_result.ok)
        self.assertEqual(old_result.freshness, "stale")
        self.assertIn("phiên cũ", old_result.error)
        self.assertFalse(lagged_result.ok)
        self.assertEqual(lagged_result.freshness, "stale")
        self.assertEqual(lagged_result.lag_seconds, 30 * 60)
        self.assertIn("30.0 phút", lagged_result.error)

    def test_intraday_future_and_session_mismatch_are_rejected(self):
        fetched_at = pd.Timestamp("2026-08-14 10:00:00", tz="Asia/Ho_Chi_Minh")
        future = pd.DataFrame(
            {"time": ["2026-08-14 10:01:00"], "price": [32.4]}
        )
        outside_session = pd.DataFrame(
            {"time": ["2026-08-14 08:30:00"], "price": [32.4]}
        )
        with (
            mock.patch.object(loader, "Quote", _FakeQuote),
            mock.patch.object(loader, "vietnam_now", return_value=fetched_at),
        ):
            _FakeQuote.intraday_payloads[("KBS", "CTG")] = future
            future_result = loader.fetch_intraday("CTG", source="KBS")
            _FakeQuote.intraday_payloads[("KBS", "CTG")] = outside_session
            session_result = loader.fetch_intraday("CTG", source="KBS")

        self.assertFalse(future_result.ok)
        self.assertEqual(future_result.freshness, "future")
        self.assertLess(future_result.lag_seconds, 0)
        self.assertFalse(session_result.ok)
        self.assertEqual(session_result.freshness, "session_mismatch")

    def test_intraday_time_only_is_ambiguous_outside_vietnam_session(self):
        fetched_at = pd.Timestamp("2026-08-14 18:00:00", tz="Asia/Ho_Chi_Minh")
        _FakeQuote.intraday_payloads[("KBS", "CTG")] = pd.DataFrame(
            {"time": ["14:29:00"], "price": [32.4]}
        )
        with (
            mock.patch.object(loader, "Quote", _FakeQuote),
            mock.patch.object(loader, "vietnam_now", return_value=fetched_at),
        ):
            result = loader.fetch_intraday("CTG", source="KBS")

        self.assertFalse(result.ok)
        self.assertEqual(result.freshness, "ambiguous_date")
        self.assertIn("không thể suy đoán an toàn", result.error)


class UploadHardeningTests(unittest.TestCase):
    def test_valid_csv_preserves_import_contract(self):
        source = _named_buffer(b"A,B\n1,2\n3,4\n", "prices.csv")
        frame, report = cleaner.smart_import(source)
        self.assertEqual(frame.shape, (2, 2))
        self.assertIsInstance(report, str)
        self.assertEqual(cleaner.list_sheets(source), [])

    def test_rejects_unsupported_type_and_signature_mismatch(self):
        with self.assertRaises(cleaner.UploadValidationError) as unsupported:
            cleaner.validate_upload(_named_buffer(b"a,b\n1,2\n", "prices.txt"))
        self.assertEqual(unsupported.exception.code, "UNSUPPORTED_FILE_TYPE")

        invalid_xlsx = _named_buffer(b"not an office archive", "prices.xlsx")
        with self.assertRaises(cleaner.UploadValidationError) as mismatch:
            cleaner.validate_upload(invalid_xlsx)
        self.assertEqual(mismatch.exception.code, "FILE_SIGNATURE_MISMATCH")
        self.assertEqual(cleaner.list_sheets(invalid_xlsx), [])
        with self.assertRaises(cleaner.UploadValidationError):
            cleaner.list_sheets(invalid_xlsx, strict=True)

    def test_enforces_upload_and_table_limits(self):
        source = _named_buffer(b"A\n1\n2\n", "prices.csv")
        with mock.patch.object(cleaner, "MAX_UPLOAD_BYTES", 4):
            with self.assertRaises(cleaner.UploadValidationError) as too_large:
                cleaner.validate_upload(source)
        self.assertEqual(too_large.exception.code, "FILE_TOO_LARGE")

        source = _named_buffer(b"A\n1\n2\n", "prices.csv")
        with mock.patch.object(cleaner, "MAX_ROWS", 1):
            with self.assertRaises(cleaner.UploadValidationError) as table_too_large:
                cleaner.read_raw(source)
        self.assertEqual(table_too_large.exception.code, "TABLE_TOO_LARGE")

    def test_valid_xlsx_is_inspected_and_parsed(self):
        source = io.BytesIO()
        with pd.ExcelWriter(source, engine="openpyxl") as writer:
            pd.DataFrame({"price": [10.0, 11.0]}).to_excel(
                writer, sheet_name="Prices", index=False
            )
        source.name = "prices.xlsx"

        report = cleaner.validate_upload(source)
        self.assertGreater(report.details["archive_entries"], 0)
        self.assertEqual(cleaner.list_sheets(source, strict=True), ["Prices"])
        parsed = cleaner.read_raw(source, sheet="Prices")
        self.assertEqual(parsed.shape, (2, 1))


class SafeExpressionTests(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame(
            {"X": [1.0, 2.0, 4.0, 8.0], "Y": [10.0, 12.0, 15.0, 19.0]}
        )

    def test_supported_math_lag_difference_and_trend(self):
        result = eviews.eviews_expr_to_series(
            "LOG(X) + D(Y) + X(-1) + @TREND", self.frame
        )
        self.assertTrue(pd.isna(result.iloc[0]))
        self.assertAlmostEqual(result.iloc[1], np.log(2.0) + 2.0 + 1.0 + 1.0)
        self.assertTrue(result.index.equals(self.frame.index))

    def test_comparisons_return_integer_dummy(self):
        result = eviews.eviews_expr_to_series("(X > 2) & (Y <= 19)", self.frame)
        self.assertEqual(result.tolist(), [0, 0, 1, 1])

    def test_disallows_non_allowlisted_syntax_and_unbounded_power(self):
        with self.assertRaises(eviews.ExpressionValidationError) as attribute:
            eviews.eviews_expr_to_series("X.shape", self.frame)
        self.assertEqual(attribute.exception.code, "UNSUPPORTED_SYNTAX")

        with self.assertRaises(eviews.ExpressionValidationError) as subscript:
            eviews.eviews_expr_to_series("X[0]", self.frame)
        self.assertEqual(subscript.exception.code, "UNSUPPORTED_SYNTAX")

        with self.assertRaises(eviews.ExpressionValidationError) as exponent:
            eviews.eviews_expr_to_series("X ** 11", self.frame)
        self.assertEqual(exponent.exception.code, "UNBOUNDED_POWER")

    def test_rejects_non_finite_and_overly_complex_results(self):
        with self.assertRaises(eviews.ExpressionValidationError) as division:
            eviews.eviews_expr_to_series("X / 0", self.frame)
        self.assertEqual(division.exception.code, "NON_FINITE_RESULT")

        formula = "+".join(["X"] * 70)
        with self.assertRaises(eviews.ExpressionValidationError) as complex_expression:
            eviews.eviews_expr_to_series(formula, self.frame)
        self.assertIn(
            complex_expression.exception.code,
            {"EXPRESSION_TOO_COMPLEX", "EXPRESSION_TOO_DEEP"},
        )

    def test_genr_contract_and_html_escaping(self):
        response = eviews.parse_and_execute_command("GENR Z = X * 2", self.frame)
        self.assertTrue(response.get("success"))
        self.assertEqual(response["data"]["Z"].tolist(), [2.0, 4.0, 8.0, 16.0])

        invalid = eviews.parse_and_execute_command("GENR 1Z = X", self.frame)
        self.assertIn("error", invalid)
        output = eviews.format_eviews_output({"error": "<unsafe label>"})
        self.assertNotIn("<unsafe label>", output)
        self.assertIn("&lt;unsafe label&gt;", output)


if __name__ == "__main__":
    unittest.main()
