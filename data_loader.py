"""Validated market-data ingestion for the Quant App.

The public ``fetch_data`` function keeps the original successful-return contract
(a price ``DataFrame``), but it now fails closed when any requested instrument is
missing or the common sample is not trustworthy.  Callers that want structured
errors without exceptions can use ``fetch_data_result``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
from typing import Any, Iterable

import numpy as np
import pandas as pd


def _disable_vnstock_import_side_effects() -> None:
    """Keep vnstock imports from mutating the machine or starting telemetry.

    Vnstock initializes vnai during ordinary market-data calls.  That
    initialization writes terms/editor files, inspects the local Git checkout,
    and queues system metadata.  None of it is required for Quote access, so
    replace only those initialization hooks before importing vnstock.
    """

    # vnai inspects Git during import.  On Windows its decoder is CP1252, while
    # Git emits this repository's Vietnamese path as UTF-8.  Import from the
    # non-repository home directory to avoid that vendor bug, then restore cwd.
    original_cwd = Path.cwd()
    try:
        os.chdir(Path.home())
        try:
            import vnai
            import vnai.scope.profile  # noqa: F401 - initialize outside the repo
        except ImportError:
            return
    finally:
        os.chdir(original_cwd)

    def _skip_vnai_initialization(*_args: Any, **_kwargs: Any) -> None:
        return None

    vnai.setup = _skip_vnai_initialization
    vnai.tc_init = _skip_vnai_initialization
    vnai.setup_agent_environment = _skip_vnai_initialization
    vnai.async_setup_agent_environment = _skip_vnai_initialization


_disable_vnstock_import_side_effects()
from vnstock.api.quote import Quote


MAX_TICKERS = 20
MAX_DATE_RANGE_DAYS = 3655
DEFAULT_MIN_COVERAGE = 0.70
DEFAULT_MAX_STALENESS_BUSINESS_DAYS = 5
DEFAULT_MIN_OBSERVATIONS = 3
# KBS/VCI are Vietnamese brokers and are the most accurate locally, but both
# IP-block Streamlit Cloud (every ticker returns PROVIDER_ERROR there). MSN is
# Microsoft's global source and stays reachable from cloud IPs, so it is kept as
# a last-resort fallback that keeps the deployed app working when the VN brokers
# are blocked. See _MSN_PRICE_SCALE below for the unit-normalisation MSN needs.
DEFAULT_DATA_SOURCES = ("KBS", "VCI", "MSN")

# MSN quotes VN equities in absolute VND (e.g. FPT ~109,000) whereas VCI/KBS use
# the "nghìn đồng" convention (~109). Index series (VNINDEX, VN30, ...) carry no
# such 1000x factor. We divide MSN equity OHLC by this scale so absolute-price
# features (paper portfolio, investment desk) stay consistent across sources.
# Return-based analytics (SIM, Markowitz, backtest) are scale-invariant already.
_MSN_PRICE_SCALE = 1000.0
_INDEX_SYMBOLS = frozenset(
    {
        "VNINDEX",
        "VN30",
        "VN100",
        "VNXALL",
        "VNX50",
        "HNXINDEX",
        "HNX",
        "HNX30",
        "UPCOMINDEX",
        "UPCOM",
    }
)
_MSN_PRICE_COLUMNS = ("open", "high", "low", "close")
_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,19}$")
_SOURCE_RE = re.compile(r"^[A-Z][A-Z0-9_-]{1,15}$")
_SOURCE_LIST_SPLIT_RE = re.compile(r"[\s,;|]+")


@dataclass(frozen=True)
class FetchIssue:
    """A machine-readable ingestion warning or error."""

    code: str
    message: str
    ticker: str | None = None
    severity: str = "error"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "ticker": self.ticker,
            "severity": self.severity,
            "details": dict(self.details),
        }


@dataclass
class FetchReport:
    """Provenance and data-quality facts for one fetch operation."""

    requested_tickers: list[str]
    start: str
    end: str
    source: str
    issues: list[FetchIssue] = field(default_factory=list)
    per_ticker: dict[str, dict[str, Any]] = field(default_factory=dict)
    common_rows: int = 0
    common_coverage: float = 0.0
    common_staleness_business_days: int = 0

    @property
    def errors(self) -> list[FetchIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[FetchIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "requested_tickers": list(self.requested_tickers),
            "start": self.start,
            "end": self.end,
            "source": self.source,
            "common_rows": self.common_rows,
            "common_coverage": self.common_coverage,
            "common_staleness_business_days": self.common_staleness_business_days,
            "per_ticker": {k: dict(v) for k, v in self.per_ticker.items()},
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass
class FetchResult:
    data: pd.DataFrame
    report: FetchReport

    @property
    def ok(self) -> bool:
        return self.report.ok


class DataFetchError(RuntimeError):
    """Raised when a requested portfolio cannot be fetched atomically."""

    def __init__(self, report: FetchReport):
        self.report = report
        source_names = [part.strip() for part in report.source.split(",") if part.strip()]
        all_sources_failed = any(
            issue.code == "ALL_DATA_SOURCES_FAILED" for issue in report.errors
        )
        if all_sources_failed and source_names:
            provider_errors = [
                issue for issue in report.errors if issue.code == "PROVIDER_ERROR"
            ]
            sample = []
            for issue in provider_errors[:4]:
                source = issue.details.get("source")
                subject = issue.ticker or "request"
                sample.append(
                    f"{source}:{subject}:PROVIDER_ERROR"
                    if source
                    else f"{subject}:PROVIDER_ERROR"
                )
            if len(provider_errors) > len(sample):
                sample.append(f"+{len(provider_errors) - len(sample)} more")
            summary = "; ".join(sample) or "unknown error"
            super().__init__(
                "Market-data validation failed after trying sources "
                f"{', '.join(source_names)} ({summary})."
            )
            return
        summary = "; ".join(
            f"{issue.ticker or 'request'}:{issue.code}" for issue in report.errors
        )
        super().__init__(f"Market-data validation failed ({summary or 'unknown error'}).")


class DataQualityError(ValueError):
    """Raised when local price data cannot produce trustworthy returns."""


def _empty_result(report: FetchReport) -> FetchResult:
    data = pd.DataFrame()
    data.attrs["fetch_report"] = report.to_dict()
    return FetchResult(data=data, report=report)


def _normalise_tickers(tickers: Iterable[str] | str) -> list[str]:
    if isinstance(tickers, str):
        tickers = tickers.split(",")
    if tickers is None:
        return []
    try:
        values = list(tickers)
    except TypeError as exc:
        raise ValueError("tickers must be a string or an iterable of strings") from exc
    result: list[str] = []
    for raw in values:
        if not isinstance(raw, str):
            raise ValueError("every ticker must be a string")
        ticker = str(raw).strip().upper()
        if ticker and ticker not in result:
            result.append(ticker)
    return result


def _source_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = _SOURCE_LIST_SPLIT_RE.split(value)
    else:
        try:
            raw_values = list(value)
        except TypeError as exc:
            raise ValueError("source must be a string or an iterable of strings") from exc
        values = []
        for item in raw_values:
            if not isinstance(item, str):
                raise ValueError("every source must be a string")
            values.extend(_SOURCE_LIST_SPLIT_RE.split(item))
    sources: list[str] = []
    for raw in values:
        source_name = str(raw).strip().upper()
        if source_name and source_name not in sources:
            sources.append(source_name)
    return sources


def _normalise_source_order(
    source: Any = None, fallback_sources: Any = None
) -> list[str]:
    configured = os.getenv("QUANT_APP_DATA_SOURCES") if source is None else None
    sources = _source_values(source if source is not None else configured)
    if not sources:
        sources = list(DEFAULT_DATA_SOURCES)
    for fallback in _source_values(fallback_sources):
        if fallback not in sources:
            sources.append(fallback)
    if not sources:
        raise ValueError("at least one market-data source is required")
    if any(not _SOURCE_RE.fullmatch(source_name) for source_name in sources):
        raise ValueError("source has an invalid format")
    return sources


def _normalise_date(value: Any, field_name: str) -> pd.Timestamp:
    try:
        stamp = pd.Timestamp(value)
    except Exception as exc:
        raise ValueError(f"{field_name} is not a valid date") from exc
    if pd.isna(stamp):
        raise ValueError(f"{field_name} is not a valid date")
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert(None)
    return stamp.normalize()


def _business_dates(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    effective_end = min(end, pd.Timestamp.today().normalize())
    if start > effective_end:
        return pd.DatetimeIndex([])
    return pd.bdate_range(start=start, end=effective_end)


def _coverage(index: pd.DatetimeIndex, expected: pd.DatetimeIndex) -> float:
    if len(expected) == 0:
        return 0.0
    observed = pd.DatetimeIndex(index).normalize().unique()
    return float(len(observed.intersection(expected)) / len(expected))


def _business_day_staleness(latest: pd.Timestamp, expected: pd.DatetimeIndex) -> int:
    if len(expected) == 0:
        return 0
    return int((expected > latest.normalize()).sum())


def _constant_run_length(values: np.ndarray, *, from_start: bool) -> int:
    if len(values) == 0:
        return 0
    sample = values if from_start else values[::-1]
    reference = sample[0]
    same = np.isclose(sample, reference, rtol=1e-10, atol=1e-12, equal_nan=False)
    changed = np.flatnonzero(~same)
    return int(changed[0]) if len(changed) else len(sample)


def _constant_sequence_issue(
    work: pd.DataFrame, ticker: str
) -> FetchIssue | None:
    """Detect obviously synthetic/stale constant prefixes and tails.

    A constant series is always rejected.  A prefix/tail is rejected only when
    it is long and either accompanied by zero volume or exceptionally long when
    volume is unavailable.  This is deliberately conservative to avoid trimming
    legitimate illiquid trading periods silently.
    """

    closes = work["close"].to_numpy(dtype=float)
    if len(closes) < 3:
        return None
    if np.all(np.isclose(closes, closes[0], rtol=1e-10, atol=1e-12)):
        return FetchIssue(
            code="CONSTANT_SERIES",
            ticker=ticker,
            message="All close prices are constant; returns and risk are not identifiable.",
            details={"rows": len(closes), "close": float(closes[0])},
        )

    has_volume = "volume" in work.columns
    volume = (
        pd.to_numeric(work["volume"], errors="coerce") if has_volume else None
    )
    for side, from_start in (("prefix", True), ("tail", False)):
        run_length = _constant_run_length(closes, from_start=from_start)
        if run_length < 10:
            continue
        run_frame = work.iloc[:run_length] if from_start else work.iloc[-run_length:]
        span_days = int((run_frame.index.max() - run_frame.index.min()).days)
        run_volume = volume.iloc[:run_length] if from_start and volume is not None else None
        if not from_start and volume is not None:
            run_volume = volume.iloc[-run_length:]
        zero_volume = bool(
            run_volume is not None
            and run_volume.fillna(0).le(0).all()
        )
        suspicious = span_days >= 14 and (zero_volume or run_length >= 20)
        if suspicious:
            code = (
                "SUSPICIOUS_CONSTANT_PREFIX"
                if side == "prefix"
                else "SUSPICIOUS_STALE_TAIL"
            )
            return FetchIssue(
                code=code,
                ticker=ticker,
                message=(
                    "A long constant-price segment was detected; it may be "
                    "pre-listing placeholder or stale data."
                ),
                details={
                    "side": side,
                    "rows": run_length,
                    "span_days": span_days,
                    "zero_volume": zero_volume,
                },
            )
    return None


def _clean_symbol_frame(
    raw: Any,
    ticker: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    expected: pd.DatetimeIndex,
    *,
    min_coverage: float,
    max_staleness_business_days: int,
    min_observations: int,
) -> tuple[pd.DataFrame | None, dict[str, Any], list[FetchIssue]]:
    issues: list[FetchIssue] = []
    metadata: dict[str, Any] = {"rows_received": 0, "rows_valid": 0}
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        issues.append(
            FetchIssue(
                code="EMPTY_RESPONSE",
                ticker=ticker,
                message="The provider returned no rows.",
            )
        )
        return None, metadata, issues
    metadata["rows_received"] = int(len(raw))
    missing = [name for name in ("time", "close") if name not in raw.columns]
    if missing:
        issues.append(
            FetchIssue(
                code="SCHEMA_MISMATCH",
                ticker=ticker,
                message="Provider response is missing required columns.",
                details={"missing": missing, "columns": list(map(str, raw.columns))},
            )
        )
        return None, metadata, issues

    columns = ["time", "close"] + (["volume"] if "volume" in raw.columns else [])
    work = raw[columns].copy()
    work["time"] = pd.to_datetime(work["time"], errors="coerce")
    invalid_times = int(work["time"].isna().sum())
    if invalid_times:
        issues.append(
            FetchIssue(
                code="INVALID_TIMESTAMPS",
                ticker=ticker,
                message="Rows with invalid timestamps were rejected.",
                details={"count": invalid_times},
            )
        )
        return None, metadata, issues
    if getattr(work["time"].dt, "tz", None) is not None:
        work["time"] = work["time"].dt.tz_convert(None)
    work["time"] = work["time"].dt.normalize()
    work["close"] = pd.to_numeric(work["close"], errors="coerce")
    in_range = work["time"].dt.normalize().between(start, end, inclusive="both")
    work = work.loc[in_range].copy()
    invalid_closes = (~np.isfinite(work["close"])) | work["close"].le(0)
    if bool(invalid_closes.any()):
        issues.append(
            FetchIssue(
                code="INVALID_CLOSE_VALUES",
                ticker=ticker,
                message="Non-finite, zero, or negative close prices were found.",
                details={"count": int(invalid_closes.sum())},
            )
        )
        return None, metadata, issues

    before_dedup = len(work)
    work = work.sort_values("time", kind="mergesort").drop_duplicates(
        "time", keep="last"
    )
    duplicate_count = before_dedup - len(work)
    if duplicate_count:
        issues.append(
            FetchIssue(
                code="DUPLICATE_TIMESTAMPS_DROPPED",
                ticker=ticker,
                severity="warning",
                message="Duplicate timestamps were deterministically reduced to the last row.",
                details={"count": int(duplicate_count)},
            )
        )
    work = work.set_index("time")
    metadata["rows_valid"] = int(len(work))
    if len(work) < min_observations:
        issues.append(
            FetchIssue(
                code="INSUFFICIENT_OBSERVATIONS",
                ticker=ticker,
                message="Too few valid observations remain in the requested date range.",
                details={"rows": len(work), "minimum": min_observations},
            )
        )
        return None, metadata, issues

    constant_issue = _constant_sequence_issue(work, ticker)
    if constant_issue:
        issues.append(constant_issue)
        return None, metadata, issues

    ticker_coverage = _coverage(work.index, expected)
    latest = pd.Timestamp(work.index.max()).normalize()
    staleness = _business_day_staleness(latest, expected)
    metadata.update(
        {
            "start": pd.Timestamp(work.index.min()).isoformat(),
            "end": pd.Timestamp(work.index.max()).isoformat(),
            "coverage": ticker_coverage,
            "staleness_business_days": staleness,
            "duplicates_dropped": int(duplicate_count),
        }
    )
    if ticker_coverage < min_coverage:
        issues.append(
            FetchIssue(
                code="INSUFFICIENT_COVERAGE",
                ticker=ticker,
                message="Date coverage is below the required threshold.",
                details={
                    "coverage": ticker_coverage,
                    "minimum": min_coverage,
                    "expected_business_days": len(expected),
                },
            )
        )
        return None, metadata, issues
    if staleness > max_staleness_business_days:
        issues.append(
            FetchIssue(
                code="STALE_SERIES",
                ticker=ticker,
                message="The latest observation is too far behind the requested end date.",
                details={
                    "latest": latest.date().isoformat(),
                    "staleness_business_days": staleness,
                    "maximum": max_staleness_business_days,
                },
            )
        )
        return None, metadata, issues

    return work[["close"]].rename(columns={"close": ticker}), metadata, issues


def _normalise_msn_prices(raw: Any, ticker: str) -> Any:
    """Rescale MSN equity OHLC (absolute VND) to the nghìn-đồng convention.

    MSN reports VN equity prices ~1000x larger than VCI/KBS; indices are already
    on the same scale, so they are left untouched. Anything we cannot safely
    recognise as a DataFrame with price columns is returned unchanged.
    """
    if ticker.upper() in _INDEX_SYMBOLS:
        return raw
    if raw is None or not hasattr(raw, "columns") or getattr(raw, "empty", True):
        return raw
    price_cols = [col for col in _MSN_PRICE_COLUMNS if col in raw.columns]
    if not price_cols:
        return raw
    raw = raw.copy()
    raw[price_cols] = raw[price_cols] / _MSN_PRICE_SCALE
    return raw


def _fetch_data_result_from_source(
    requested: list[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
    source_name: str,
    expected: pd.DatetimeIndex,
    *,
    min_coverage: float,
    max_staleness_business_days: int,
    min_observations: int,
) -> FetchResult:
    report = FetchReport(
        requested_tickers=requested,
        start=start.date().isoformat(),
        end=end.date().isoformat(),
        source=source_name,
    )
    frames: dict[str, pd.DataFrame] = {}
    for ticker in requested:
        try:
            raw = Quote(symbol=ticker, source=source_name).history(
                start=start.date().isoformat(), end=end.date().isoformat()
            )
            if source_name == "MSN":
                raw = _normalise_msn_prices(raw, ticker)
        except Exception as exc:
            report.issues.append(
                FetchIssue(
                    code="PROVIDER_ERROR",
                    ticker=ticker,
                    message="The market-data provider request failed.",
                    details={
                        "source": source_name,
                        "exception_type": type(exc).__name__,
                        "reason": str(exc),
                    },
                )
            )
            continue
        frame, metadata, issues = _clean_symbol_frame(
            raw,
            ticker,
            start,
            end,
            expected,
            min_coverage=float(min_coverage),
            max_staleness_business_days=int(max_staleness_business_days),
            min_observations=int(min_observations),
        )
        metadata["source"] = source_name
        report.per_ticker[ticker] = metadata
        report.issues.extend(issues)
        if frame is not None:
            frames[ticker] = frame

    # Never return a partial portfolio: any failed symbol invalidates the result.
    if report.errors or set(frames) != set(requested):
        missing = [ticker for ticker in requested if ticker not in frames]
        if missing and not any(
            issue.code == "INCOMPLETE_PORTFOLIO" for issue in report.issues
        ):
            report.issues.append(
                FetchIssue(
                    code="INCOMPLETE_PORTFOLIO",
                    message="No partial portfolio is returned when any ticker fails validation.",
                    details={"missing_or_invalid": missing},
                )
            )
        return _empty_result(report)

    final_df = pd.concat([frames[ticker] for ticker in requested], axis=1, join="inner")
    in_range = (final_df.index.normalize() >= start) & (
        final_df.index.normalize() <= end
    )
    final_df = final_df.loc[in_range]
    final_df = final_df.sort_index().loc[lambda df: ~df.index.duplicated(keep="last")]
    final_df = final_df.replace([np.inf, -np.inf], np.nan).dropna(how="any")
    report.common_rows = int(len(final_df))
    report.common_coverage = _coverage(final_df.index, expected)
    if len(final_df) < int(min_observations):
        report.issues.append(
            FetchIssue(
                code="INSUFFICIENT_COMMON_OBSERVATIONS",
                message="Too few dates are shared by every requested ticker.",
                details={"rows": len(final_df), "minimum": min_observations},
            )
        )
        return _empty_result(report)
    common_latest = pd.Timestamp(final_df.index.max()).normalize()
    report.common_staleness_business_days = _business_day_staleness(
        common_latest, expected
    )
    if report.common_staleness_business_days > int(max_staleness_business_days):
        report.issues.append(
            FetchIssue(
                code="STALE_COMMON_SAMPLE",
                message="The latest date shared by the complete portfolio is too stale.",
                details={
                    "latest": common_latest.date().isoformat(),
                    "staleness_business_days": report.common_staleness_business_days,
                    "maximum": int(max_staleness_business_days),
                },
            )
        )
        return _empty_result(report)
    if report.common_coverage < float(min_coverage):
        report.issues.append(
            FetchIssue(
                code="INSUFFICIENT_COMMON_COVERAGE",
                message="The aligned portfolio sample has insufficient date coverage.",
                details={
                    "coverage": report.common_coverage,
                    "minimum": min_coverage,
                    "expected_business_days": len(expected),
                },
            )
        )
        return _empty_result(report)

    final_df = final_df[requested]
    final_df.attrs["fetch_report"] = report.to_dict()
    return FetchResult(data=final_df, report=report)


def _combine_failed_fetch_reports(reports: list[FetchReport]) -> FetchResult:
    if not reports:
        empty_report = FetchReport(
            requested_tickers=[],
            start="",
            end="",
            source=",".join(DEFAULT_DATA_SOURCES),
        )
        empty_report.issues.append(
            FetchIssue(
                code="ALL_DATA_SOURCES_FAILED",
                message="No configured market-data source returned a complete validated portfolio.",
            )
        )
        return _empty_result(empty_report)
    combined = FetchReport(
        requested_tickers=list(reports[0].requested_tickers),
        start=reports[0].start,
        end=reports[0].end,
        source=",".join(report.source for report in reports),
    )
    combined.issues.append(
        FetchIssue(
            code="ALL_DATA_SOURCES_FAILED",
            message="No configured market-data source returned a complete validated portfolio.",
            details={"sources": [report.source for report in reports]},
        )
    )
    for report in reports:
        for ticker, metadata in report.per_ticker.items():
            combined.per_ticker[f"{report.source}:{ticker}"] = dict(metadata)
        for issue in report.issues:
            details = dict(issue.details)
            details.setdefault("source", report.source)
            combined.issues.append(
                FetchIssue(
                    code=issue.code,
                    message=issue.message,
                    ticker=issue.ticker,
                    severity=issue.severity,
                    details=details,
                )
            )
    return _empty_result(combined)


def fetch_data_result(
    tickers: Iterable[str] | str,
    start_date: Any,
    end_date: Any,
    *,
    source: Any = None,
    fallback_sources: Any = None,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
    max_staleness_business_days: int = DEFAULT_MAX_STALENESS_BUSINESS_DAYS,
    min_observations: int = DEFAULT_MIN_OBSERVATIONS,
) -> FetchResult:
    """Fetch and validate a complete portfolio without returning partial data."""

    try:
        requested = _normalise_tickers(tickers)
        ticker_input_error = None
    except ValueError as exc:
        requested = []
        ticker_input_error = str(exc)
    report = FetchReport(
        requested_tickers=requested,
        start=str(start_date),
        end=str(end_date),
        source="",
    )
    if ticker_input_error:
        report.issues.append(
            FetchIssue(code="INVALID_REQUEST", message=ticker_input_error)
        )
        return _empty_result(report)
    try:
        start = _normalise_date(start_date, "start_date")
        end = _normalise_date(end_date, "end_date")
        report.start, report.end = start.date().isoformat(), end.date().isoformat()
        if start > end:
            raise ValueError("start_date must be on or before end_date")
        if end > pd.Timestamp.today().normalize():
            raise ValueError("end_date cannot be in the future")
        if (end - start).days > MAX_DATE_RANGE_DAYS:
            raise ValueError(
                f"date range exceeds the {MAX_DATE_RANGE_DAYS}-day safety limit"
            )
        if not 0 < float(min_coverage) <= 1:
            raise ValueError("min_coverage must be in (0, 1]")
        source_order = _normalise_source_order(source, fallback_sources)
        report.source = ",".join(source_order)
        if int(max_staleness_business_days) < 0 or int(min_observations) < 2:
            raise ValueError("staleness and observation limits are invalid")
    except (TypeError, ValueError) as exc:
        report.issues.append(
            FetchIssue(code="INVALID_REQUEST", message=str(exc))
        )
        return _empty_result(report)

    if not requested:
        report.issues.append(
            FetchIssue(code="NO_TICKERS", message="At least one ticker is required.")
        )
        return _empty_result(report)
    if len(requested) > MAX_TICKERS:
        report.issues.append(
            FetchIssue(
                code="TOO_MANY_TICKERS",
                message=f"At most {MAX_TICKERS} tickers may be fetched at once.",
                details={"requested": len(requested), "maximum": MAX_TICKERS},
            )
        )
        return _empty_result(report)
    invalid_tickers = [ticker for ticker in requested if not _TICKER_RE.fullmatch(ticker)]
    if invalid_tickers:
        report.issues.append(
            FetchIssue(
                code="INVALID_TICKERS",
                message="One or more ticker symbols have an invalid format.",
                details={"tickers": invalid_tickers},
            )
        )
        return _empty_result(report)

    expected = _business_dates(start, end)
    if len(expected) < int(min_observations):
        report.issues.append(
            FetchIssue(
                code="REQUEST_WINDOW_TOO_SHORT",
                message="The requested window has too few business days.",
                details={"business_days": len(expected), "minimum": min_observations},
            )
        )
        return _empty_result(report)

    failed_reports: list[FetchReport] = []
    for source_name in source_order:
        result = _fetch_data_result_from_source(
            requested,
            start,
            end,
            source_name,
            expected,
            min_coverage=float(min_coverage),
            max_staleness_business_days=int(max_staleness_business_days),
            min_observations=int(min_observations),
        )
        if result.ok:
            if failed_reports:
                result.report.issues.append(
                    FetchIssue(
                        code="DATA_SOURCE_FALLBACK_USED",
                        message="A fallback market-data source returned the complete portfolio.",
                        severity="warning",
                        details={
                            "selected_source": result.report.source,
                            "failed_sources": [
                                failed_report.source for failed_report in failed_reports
                            ],
                        },
                    )
                )
                result.data.attrs["fetch_report"] = result.report.to_dict()
            return result
        failed_reports.append(result.report)

    return _combine_failed_fetch_reports(failed_reports)


def fetch_data(tickers, start_date, end_date, **kwargs):
    """Backward-compatible adapter returning a validated price DataFrame.

    Unlike the previous implementation, failures raise ``DataFetchError`` rather
    than returning a silently incomplete portfolio.
    """

    result = fetch_data_result(tickers, start_date, end_date, **kwargs)
    if not result.ok:
        raise DataFetchError(result.report)
    return result.data


def calculate_returns(prices_df):
    """Calculate aligned daily log returns from validated positive prices."""

    if not isinstance(prices_df, pd.DataFrame):
        raise DataQualityError("prices_df must be a pandas DataFrame")
    if prices_df.empty:
        return pd.DataFrame(index=prices_df.index, columns=prices_df.columns, dtype=float)
    data = prices_df.copy()
    data = data.sort_index().loc[lambda df: ~df.index.duplicated(keep="last")]
    data = data.apply(pd.to_numeric, errors="coerce")
    data = data.where(data > 0)
    returns = np.log(data / data.shift(1))
    returns = returns.replace([np.inf, -np.inf], np.nan).dropna(how="any")
    if returns.empty:
        raise DataQualityError("No aligned finite log returns could be calculated")
    returns.attrs.update(prices_df.attrs)
    return returns
