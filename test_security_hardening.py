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

    def __init__(self, symbol: str, source: str):
        self.symbol = symbol
        self.source = source

    def history(self, start: str, end: str):
        source_key = (self.source, self.symbol)
        payload = (
            self.payloads[source_key]
            if source_key in self.payloads
            else self.payloads[self.symbol]
        )
        if isinstance(payload, Exception):
            raise payload
        return payload.copy()


class MarketDataHardeningTests(unittest.TestCase):
    def setUp(self):
        _FakeQuote.payloads = {}

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
