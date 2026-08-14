"""Validated market-data ingestion for the Quant App.

The public ``fetch_data`` function keeps the original successful-return contract
(a price ``DataFrame``), but it now fails closed when any requested instrument is
missing or the common sample is not trustworthy.  Callers that want structured
errors without exceptions can use ``fetch_data_result``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
import os
from pathlib import Path
import re
import threading
from time import monotonic
from typing import Any, Iterable
from zoneinfo import ZoneInfo

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
VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
INTRADAY_MAX_LAG_SECONDS = 15 * 60
INTRADAY_SESSION_START = time(9, 0)
INTRADAY_SESSION_END = time(15, 0)
HISTORY_SOURCE_COOLDOWN_SECONDS = 5 * 60
INTRADAY_SOURCE_COOLDOWN_SECONDS = 60
# Prefer the Vietnam-focused sources, then use MSN as a last-resort fallback.
# Provider reachability can change by network, account and deployment region;
# the circuit breaker below learns only from current process-local failures
# instead of assuming that a provider is permanently blocked.  See
# _MSN_PRICE_SCALE below for the unit normalisation MSN needs.
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
# Only these providers expose an intraday (matched-order) endpoint; MSN has none.
_INTRADAY_SOURCES = ("KBS", "VCI")
_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,19}$")
_SOURCE_RE = re.compile(r"^[A-Z][A-Z0-9_-]{1,15}$")
_SOURCE_LIST_SPLIT_RE = re.compile(r"[\s,;|]+")
_TIME_ONLY_RE = re.compile(
    r"^\s*(?P<hour>\d{1,2}):(?P<minute>\d{2})"
    r"(?::(?P<second>\d{2})(?:\.(?P<microsecond>\d{1,6}))?)?\s*$"
)
_SOURCE_CIRCUIT_LOCK = threading.Lock()
_SOURCE_CIRCUIT_OPEN_UNTIL: dict[tuple[str, str], float] = {}


def vietnam_now() -> pd.Timestamp:
    """Return one timezone-aware wall-clock timestamp for Vietnam."""

    return pd.Timestamp.now(tz=VIETNAM_TZ)


def _vietnam_today_naive() -> pd.Timestamp:
    """Return Vietnam's current calendar date as a naive normalized stamp."""

    return vietnam_now().tz_localize(None).normalize()


def _source_cooldown_remaining(operation: str, source_name: str) -> float:
    """Return remaining cooldown using a clock immune to wall-clock changes."""

    key = (str(operation).lower(), str(source_name).upper())
    now = monotonic()
    with _SOURCE_CIRCUIT_LOCK:
        open_until = _SOURCE_CIRCUIT_OPEN_UNTIL.get(key)
        if open_until is None:
            return 0.0
        remaining = open_until - now
        if remaining <= 0:
            _SOURCE_CIRCUIT_OPEN_UNTIL.pop(key, None)
            return 0.0
        return float(remaining)


def _open_source_circuit(operation: str, source_name: str, seconds: float) -> None:
    """Open or extend one provider-operation cooldown without storing results."""

    key = (str(operation).lower(), str(source_name).upper())
    open_until = monotonic() + max(0.0, float(seconds))
    with _SOURCE_CIRCUIT_LOCK:
        existing = _SOURCE_CIRCUIT_OPEN_UNTIL.get(key, 0.0)
        _SOURCE_CIRCUIT_OPEN_UNTIL[key] = max(existing, open_until)


def _reset_source_circuit(operation: str, source_name: str) -> None:
    key = (str(operation).lower(), str(source_name).upper())
    with _SOURCE_CIRCUIT_LOCK:
        _SOURCE_CIRCUIT_OPEN_UNTIL.pop(key, None)


def _reset_source_circuit_breakers() -> None:
    """Clear process-local breaker state; primarily for deterministic tests."""

    with _SOURCE_CIRCUIT_LOCK:
        _SOURCE_CIRCUIT_OPEN_UNTIL.clear()


def _source_cooldown_issue(
    source_name: str,
    operation: str,
    remaining_seconds: float,
    *,
    severity: str = "error",
) -> FetchIssue:
    cooldown_seconds = (
        HISTORY_SOURCE_COOLDOWN_SECONDS
        if operation == "history"
        else INTRADAY_SOURCE_COOLDOWN_SECONDS
    )
    return FetchIssue(
        code="SOURCE_COOLDOWN",
        message=(
            "Nguồn dữ liệu thị trường (market-data source) đang tạm nghỉ sau lỗi "
            "nhà cung cấp (provider error)."
        ),
        severity=severity,
        details={
            "source": source_name,
            "operation": operation,
            "remaining_seconds": round(max(0.0, remaining_seconds), 3),
            "cooldown_seconds": cooldown_seconds,
        },
    )


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
                subject = issue.ticker or "yêu-cầu(request)"
                sample.append(
                    f"{source}:{subject}:PROVIDER_ERROR"
                    if source
                    else f"{subject}:PROVIDER_ERROR"
                )
            if len(provider_errors) > len(sample):
                sample.append(f"+{len(provider_errors) - len(sample)} lỗi khác")
            summary = "; ".join(sample) or "lỗi chưa xác định (unknown error)"
            super().__init__(
                "Kiểm định dữ liệu thị trường (market data) thất bại sau khi thử các "
                f"nguồn {', '.join(source_names)} ({summary})."
            )
            return
        summary = "; ".join(
            f"{issue.ticker or 'yêu-cầu(request)'}:{issue.code}" for issue in report.errors
        )
        super().__init__(
            "Kiểm định dữ liệu thị trường (market data) thất bại "
            f"({summary or 'lỗi chưa xác định (unknown error)'})."
        )


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
        raise ValueError(
            "Danh sách mã chứng khoán (tickers) phải là chuỗi hoặc tập chuỗi có thể lặp."
        ) from exc
    result: list[str] = []
    for raw in values:
        if not isinstance(raw, str):
            raise ValueError("Mỗi mã chứng khoán (ticker) phải là chuỗi.")
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
            raise ValueError(
                "Nguồn dữ liệu (source) phải là chuỗi hoặc tập chuỗi có thể lặp."
            ) from exc
        values = []
        for item in raw_values:
            if not isinstance(item, str):
                raise ValueError("Mỗi nguồn dữ liệu (source) phải là chuỗi.")
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
        raise ValueError(
            "Cần ít nhất một nguồn dữ liệu thị trường (market-data source)."
        )
    if any(not _SOURCE_RE.fullmatch(source_name) for source_name in sources):
        raise ValueError("Nguồn dữ liệu (source) có định dạng không hợp lệ.")
    return sources


def _normalise_date(value: Any, field_name: str) -> pd.Timestamp:
    try:
        stamp = pd.Timestamp(value)
    except Exception as exc:
        raise ValueError(f"Trường ngày {field_name} không hợp lệ.") from exc
    if pd.isna(stamp):
        raise ValueError(f"Trường ngày {field_name} không hợp lệ.")
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert(VIETNAM_TZ).tz_localize(None)
    return stamp.normalize()


def _business_dates(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    effective_end = min(end, _vietnam_today_naive())
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
            message=(
                "Mọi giá đóng cửa (close price) đều không đổi; không thể nhận diện "
                "lợi suất và rủi ro."
            ),
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
                    "Phát hiện một đoạn giá không đổi kéo dài; đây có thể là dữ liệu giữ "
                    "chỗ trước niêm yết (pre-listing placeholder) hoặc dữ liệu cũ (stale data)."
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
                message="Nhà cung cấp dữ liệu (provider) không trả về dòng nào.",
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
                message=(
                    "Phản hồi của nhà cung cấp (provider response) thiếu các cột bắt buộc."
                ),
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
                message=(
                    "Đã loại các dòng có thời điểm (timestamp) không hợp lệ."
                ),
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
                message=(
                    "Phát hiện giá đóng cửa (close price) không hữu hạn, bằng 0 hoặc âm."
                ),
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
                message=(
                    "Các thời điểm (timestamp) bị trùng đã được xử lý xác định bằng cách "
                    "giữ lại dòng cuối."
                ),
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
                message=(
                    "Khoảng ngày yêu cầu còn quá ít quan sát hợp lệ (valid observations)."
                ),
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
                message=(
                    "Mức bao phủ ngày (date coverage) thấp hơn ngưỡng yêu cầu."
                ),
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
                message=(
                    "Quan sát mới nhất chậm quá xa so với ngày kết thúc được yêu cầu."
                ),
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
    provider_error_tickers: set[str] = set()
    provider_success_count = 0
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
                    message=(
                        "Yêu cầu tới nhà cung cấp dữ liệu thị trường "
                        "(market-data provider) đã thất bại."
                    ),
                    details={
                        "source": source_name,
                        "exception_type": type(exc).__name__,
                        "reason": str(exc),
                    },
                )
            )
            provider_error_tickers.add(ticker)
            continue
        provider_success_count += 1
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

    # A breaker tracks provider reachability, not local validation quality. Open
    # it only when every requested symbol raised at the provider boundary.
    if requested and provider_error_tickers == set(requested):
        _open_source_circuit(
            "history", source_name, HISTORY_SOURCE_COOLDOWN_SECONDS
        )
    elif provider_success_count:
        _reset_source_circuit("history", source_name)

    # Never return a partial portfolio: any failed symbol invalidates the result.
    if report.errors or set(frames) != set(requested):
        missing = [ticker for ticker in requested if ticker not in frames]
        if missing and not any(
            issue.code == "INCOMPLETE_PORTFOLIO" for issue in report.issues
        ):
            report.issues.append(
                FetchIssue(
                    code="INCOMPLETE_PORTFOLIO",
                    message=(
                        "Không trả về danh mục thiếu (partial portfolio) khi bất kỳ mã "
                        "chứng khoán nào không vượt qua kiểm định."
                    ),
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
                message=(
                    "Có quá ít ngày chung giữa mọi mã chứng khoán (ticker) được yêu cầu."
                ),
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
                message=(
                    "Ngày chung mới nhất của toàn danh mục đã quá cũ (stale)."
                ),
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
                message=(
                    "Mẫu danh mục đã căn chỉnh (aligned portfolio sample) không đủ mức "
                    "bao phủ ngày."
                ),
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
                message=(
                    "Không nguồn dữ liệu thị trường (market-data source) đã cấu hình nào "
                    "trả về danh mục hoàn chỉnh đã kiểm định."
                ),
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
            message=(
                "Không nguồn dữ liệu thị trường (market-data source) đã cấu hình nào "
                "trả về danh mục hoàn chỉnh đã kiểm định."
            ),
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
            raise ValueError(
                "Ngày bắt đầu (start_date) phải trước hoặc bằng ngày kết thúc (end_date)."
            )
        if end > _vietnam_today_naive():
            raise ValueError("Ngày kết thúc (end_date) không được nằm trong tương lai.")
        if (end - start).days > MAX_DATE_RANGE_DAYS:
            raise ValueError(
                f"Khoảng ngày vượt giới hạn an toàn {MAX_DATE_RANGE_DAYS} ngày."
            )
        if not 0 < float(min_coverage) <= 1:
            raise ValueError(
                "Mức bao phủ tối thiểu (min_coverage) phải thuộc khoảng (0, 1]."
            )
        source_order = _normalise_source_order(source, fallback_sources)
        report.source = ",".join(source_order)
        if int(max_staleness_business_days) < 0 or int(min_observations) < 2:
            raise ValueError(
                "Giới hạn độ cũ dữ liệu (staleness) hoặc số quan sát không hợp lệ."
            )
    except (TypeError, ValueError) as exc:
        report.issues.append(
            FetchIssue(code="INVALID_REQUEST", message=str(exc))
        )
        return _empty_result(report)

    if not requested:
        report.issues.append(
            FetchIssue(
                code="NO_TICKERS",
                message="Cần ít nhất một mã chứng khoán (ticker).",
            )
        )
        return _empty_result(report)
    if len(requested) > MAX_TICKERS:
        report.issues.append(
            FetchIssue(
                code="TOO_MANY_TICKERS",
                message=(
                    f"Chỉ được tải tối đa {MAX_TICKERS} mã chứng khoán (tickers) mỗi lần."
                ),
                details={"requested": len(requested), "maximum": MAX_TICKERS},
            )
        )
        return _empty_result(report)
    invalid_tickers = [ticker for ticker in requested if not _TICKER_RE.fullmatch(ticker)]
    if invalid_tickers:
        report.issues.append(
            FetchIssue(
                code="INVALID_TICKERS",
                message=(
                    "Một hoặc nhiều mã chứng khoán (ticker symbol) có định dạng không hợp lệ."
                ),
                details={"tickers": invalid_tickers},
            )
        )
        return _empty_result(report)

    expected = _business_dates(start, end)
    if len(expected) < int(min_observations):
        report.issues.append(
            FetchIssue(
                code="REQUEST_WINDOW_TOO_SHORT",
                message=(
                    "Khoảng thời gian yêu cầu có quá ít ngày làm việc (business days)."
                ),
                details={"business_days": len(expected), "minimum": min_observations},
            )
        )
        return _empty_result(report)

    failed_reports: list[FetchReport] = []
    for source_name in source_order:
        cooldown_remaining = _source_cooldown_remaining("history", source_name)
        if cooldown_remaining > 0:
            cooldown_report = FetchReport(
                requested_tickers=list(requested),
                start=start.date().isoformat(),
                end=end.date().isoformat(),
                source=source_name,
            )
            cooldown_report.issues.append(
                _source_cooldown_issue(
                    source_name, "history", cooldown_remaining
                )
            )
            failed_reports.append(cooldown_report)
            continue
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
                for failed_report in failed_reports:
                    for issue in failed_report.issues:
                        if issue.code == "SOURCE_COOLDOWN":
                            result.report.issues.append(
                                FetchIssue(
                                    code=issue.code,
                                    message=issue.message,
                                    ticker=issue.ticker,
                                    severity="warning",
                                    details=dict(issue.details),
                                )
                            )
                result.report.issues.append(
                    FetchIssue(
                        code="DATA_SOURCE_FALLBACK_USED",
                        message=(
                            "Nguồn dữ liệu thị trường dự phòng (fallback source) đã trả về "
                            "danh mục hoàn chỉnh."
                        ),
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


@dataclass
class IntradayResult:
    """Matched-order ticks for one symbol, plus provenance for the UI."""

    data: pd.DataFrame
    symbol: str = ""
    page_size: int = 0
    query_signature: str = ""
    source: str = ""
    error: str = ""
    fetched_at: pd.Timestamp | None = None
    trading_date: date | None = None
    freshness: str = "unavailable"
    lag_seconds: float | None = None
    issues: list[FetchIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.symbol) and self.freshness == "fresh" and not self.data.empty

    def matches_query(self, ticker: Any, page_size: Any) -> bool:
        """Prevent a cached result from being relabelled after inputs change."""

        return self.query_signature == intraday_query_signature(ticker, page_size)

    @property
    def last_price(self) -> float | None:
        if self.data.empty or "price" not in self.data.columns:
            return None
        value = pd.to_numeric(self.data["price"], errors="coerce").dropna()
        return float(value.iloc[-1]) if len(value) else None

    @property
    def last_tick_time(self):
        if self.data.empty or "time" not in self.data.columns:
            return None
        values = self.data["time"].dropna()
        if values.empty:
            return None
        try:
            return _as_vietnam_timestamp(values.iloc[-1])
        except (TypeError, ValueError):
            return None


@dataclass
class _IntradayFrameResult:
    data: pd.DataFrame
    error: str = ""
    freshness: str = "invalid"
    trading_date: date | None = None
    lag_seconds: float | None = None


def _normalise_intraday_page_size(page_size: Any) -> int:
    try:
        size = int(page_size)
    except (TypeError, ValueError):
        size = 500
    return max(1, min(size, 5000))


def intraday_query_signature(ticker: Any, page_size: Any) -> str:
    """Canonical cache key for an intraday query."""

    symbol = str(ticker or "").strip().upper()
    return f"{symbol}:{_normalise_intraday_page_size(page_size)}"


def _as_vietnam_timestamp(value: Any) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if pd.isna(stamp):
        raise ValueError("Thiếu thời điểm (timestamp).")
    if stamp.tzinfo is None:
        return stamp.tz_localize(VIETNAM_TZ)
    return stamp.tz_convert(VIETNAM_TZ)


def _clock_from_time_only(value: Any) -> time | None:
    match = _TIME_ONLY_RE.fullmatch(str(value))
    if match is None:
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    second = int(match.group("second") or 0)
    microsecond_text = (match.group("microsecond") or "").ljust(6, "0")
    microsecond = int(microsecond_text or 0)
    try:
        return time(hour, minute, second, microsecond)
    except ValueError:
        return None


def _can_infer_intraday_date(fetched_at: pd.Timestamp) -> bool:
    local_time = fetched_at.timetz().replace(tzinfo=None)
    return (
        fetched_at.weekday() < 5
        and INTRADAY_SESSION_START <= local_time <= INTRADAY_SESSION_END
    )


def _parse_intraday_times(
    values: pd.Series,
    *,
    explicit_dates: pd.Series | None,
    fetched_at: pd.Timestamp,
) -> tuple[pd.Series | None, str]:
    """Parse provider times without borrowing the cloud server's UTC date."""

    non_missing = values.dropna()
    if non_missing.empty:
        return None, "Nhà cung cấp không trả về thời điểm khớp lệnh."

    clocks = non_missing.map(_clock_from_time_only)
    time_only = clocks.notna()
    if time_only.any() and not time_only.all():
        return None, "Nhà cung cấp trộn thời gian đầy đủ và giờ rời rạc trong cùng dữ liệu."

    parsed = pd.Series(pd.NaT, index=values.index, dtype="object")
    if time_only.all():
        if explicit_dates is not None:
            dates: dict[Any, date] = {}
            for idx in non_missing.index:
                raw_date = explicit_dates.loc[idx]
                try:
                    dates[idx] = _as_vietnam_timestamp(raw_date).date()
                except (TypeError, ValueError):
                    return None, "Ngày giao dịch đi kèm giờ khớp lệnh không hợp lệ."
        elif _can_infer_intraday_date(fetched_at):
            dates = {idx: fetched_at.date() for idx in non_missing.index}
        else:
            return (
                None,
                "Dữ liệu chỉ có giờ nhưng không có ngày giao dịch; ngoài phiên không thể suy đoán an toàn.",
            )

        for idx in non_missing.index:
            combined = datetime.combine(dates[idx], clocks.loc[idx])
            parsed.loc[idx] = pd.Timestamp(combined, tz=VIETNAM_TZ)
        return parsed, ""

    for idx, value in non_missing.items():
        try:
            parsed.loc[idx] = _as_vietnam_timestamp(value)
        except (TypeError, ValueError):
            continue
    return parsed, ""


def fetch_intraday(ticker, *, page_size=500, source=None, fallback_sources=None):
    """Fetch in-session matched-order ticks for one ticker.

    This is NOT a real-time quote feed: providers publish matched orders with a
    delay of up to several minutes and the endpoint is unavailable outside
    trading hours. The caller must surface both facts to the user, so failures
    are returned as text in ``IntradayResult.error`` instead of raising.
    """

    symbol = str(ticker or "").strip().upper()
    size = _normalise_intraday_page_size(page_size)
    signature = intraday_query_signature(symbol, size)
    if not symbol:
        return IntradayResult(
            pd.DataFrame(), symbol=symbol, page_size=size,
            query_signature=signature, error="Chưa nhập mã cổ phiếu.",
            freshness="invalid",
        )
    if not _TICKER_RE.fullmatch(symbol):
        return IntradayResult(
            pd.DataFrame(), symbol=symbol, page_size=size,
            query_signature=signature, error=f"Mã '{ticker}' không hợp lệ.",
            freshness="invalid",
        )

    source_order = _normalise_source_order(source, fallback_sources)
    # MSN exposes no intraday endpoint at all, so querying it only produces a
    # confusing AttributeError in the UI. Keep it out unless explicitly asked.
    if source is None:
        source_order = [s for s in source_order if s in _INTRADAY_SOURCES]
    if not source_order:
        return IntradayResult(
            pd.DataFrame(),
            symbol=symbol,
            page_size=size,
            query_signature=signature,
            error="Không có nguồn nào hỗ trợ dữ liệu khớp lệnh trong phiên.",
            freshness="unavailable",
        )
    problems: list[str] = []
    failure_state = "unavailable"
    last_fetched_at: pd.Timestamp | None = None
    last_trading_date: date | None = None
    last_lag_seconds: float | None = None
    issues: list[FetchIssue] = []

    for source_name in source_order:
        cooldown_remaining = _source_cooldown_remaining("intraday", source_name)
        if cooldown_remaining > 0:
            issues.append(
                _source_cooldown_issue(
                    source_name,
                    "intraday",
                    cooldown_remaining,
                    severity="warning",
                )
            )
            problems.append(
                f"{source_name}: nguồn đang tạm nghỉ còn "
                f"{cooldown_remaining:.0f} giây sau lỗi nhà cung cấp."
            )
            continue
        try:
            raw = Quote(symbol=symbol, source=source_name).intraday(page_size=size)
        except Exception as exc:
            reason = _unwrap_provider_reason(exc)
            _open_source_circuit(
                "intraday", source_name, INTRADAY_SOURCE_COOLDOWN_SECONDS
            )
            issues.append(
                FetchIssue(
                    code="PROVIDER_ERROR",
                    message=(
                        "Yêu cầu dữ liệu trong phiên tới nhà cung cấp dữ liệu thị trường "
                        "(intraday market-data provider) đã thất bại."
                    ),
                    severity="warning",
                    details={
                        "source": source_name,
                        "operation": "intraday",
                        "exception_type": type(exc).__name__,
                        "reason": reason,
                    },
                )
            )
            problems.append(
                f"{source_name}: lỗi nhà cung cấp (provider error), chi tiết nguyên văn: "
                f"{reason}"
            )
            continue

        # Empty or locally invalid data is not a provider transport failure.
        _reset_source_circuit("intraday", source_name)

        if raw is None or getattr(raw, "empty", True):
            problems.append(f"{source_name}: nhà cung cấp không trả về dữ liệu khớp lệnh.")
            continue

        fetched_at = vietnam_now()
        cleaned = _clean_intraday_frame(
            raw, symbol, source_name, fetched_at=fetched_at
        )
        last_fetched_at = fetched_at
        last_trading_date = cleaned.trading_date
        last_lag_seconds = cleaned.lag_seconds
        if cleaned.data.empty or cleaned.freshness != "fresh":
            failure_state = cleaned.freshness
            problems.append(
                f"{source_name}: {cleaned.error or 'dữ liệu khớp lệnh không đạt kiểm định.'}"
            )
            continue

        return IntradayResult(
            data=cleaned.data,
            symbol=symbol,
            page_size=size,
            query_signature=signature,
            source=source_name,
            fetched_at=fetched_at,
            trading_date=cleaned.trading_date,
            freshness=cleaned.freshness,
            lag_seconds=cleaned.lag_seconds,
            issues=issues,
        )

    return IntradayResult(
        pd.DataFrame(),
        symbol=symbol,
        page_size=size,
        query_signature=signature,
        error=" | ".join(problems) or "Không lấy được dữ liệu khớp lệnh.",
        fetched_at=last_fetched_at if last_fetched_at is not None else vietnam_now(),
        trading_date=last_trading_date,
        freshness=failure_state,
        lag_seconds=last_lag_seconds,
        issues=issues,
    )


def _unwrap_provider_reason(exc):
    """Pull the human-readable message out of tenacity's RetryError wrapper."""

    cause = exc
    for _ in range(5):
        attempt = getattr(cause, "last_attempt", None)
        if attempt is None:
            break
        try:
            attempt.result()
        except Exception as inner:  # noqa: BLE001 - we want the original text
            cause = inner
            continue
        break
    text = str(cause).strip()
    return text[:200] if text else type(cause).__name__


def _clean_intraday_frame(
    raw,
    symbol,
    source_name,
    *,
    fetched_at: pd.Timestamp | None = None,
    max_lag_seconds: int = INTRADAY_MAX_LAG_SECONDS,
) -> _IntradayFrameResult:
    """Normalise and fail-closed validate one provider's matched-order ticks."""

    frame = raw.copy()
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    fetched_at = _as_vietnam_timestamp(
        fetched_at if fetched_at is not None else vietnam_now()
    )

    provider_symbols: set[str] = set()
    metadata_symbol = str(frame.attrs.get("symbol", "") or "").strip().upper()
    if metadata_symbol:
        provider_symbols.add(metadata_symbol)
    for column in ("symbol", "ticker", "organ_code", "organcode"):
        if column in frame.columns:
            provider_symbols.update(
                str(value).strip().upper()
                for value in frame[column].dropna().unique()
                if str(value).strip()
            )
    if provider_symbols and provider_symbols != {symbol}:
        return _IntradayFrameResult(
            pd.DataFrame(),
            error=(
                f"nhà cung cấp trả mã {', '.join(sorted(provider_symbols))} "
                f"thay vì mã được yêu cầu {symbol}."
            ),
            freshness="symbol_mismatch",
        )

    metadata_source = str(frame.attrs.get("source", "") or "").strip().upper()
    if metadata_source and metadata_source != source_name:
        return _IntradayFrameResult(
            pd.DataFrame(),
            error=(
                f"siêu dữ liệu (metadata) ghi nguồn {metadata_source} thay vì nguồn truy "
                f"vấn {source_name}."
            ),
            freshness="source_mismatch",
        )

    def _first_column(candidates: tuple[str, ...]) -> str | None:
        return next((candidate for candidate in candidates if candidate in frame.columns), None)

    time_candidates = tuple(
        candidate
        for candidate in ("timestamp", "datetime", "trading_time", "tradingtime", "time", "tradingdate")
        if candidate in frame.columns
    )

    def _contains_full_timestamp(column: str) -> bool:
        for value in frame[column].dropna():
            if _clock_from_time_only(value) is not None:
                continue
            try:
                stamp = _as_vietnam_timestamp(value)
            except (TypeError, ValueError):
                continue
            if stamp.timetz().replace(tzinfo=None) != time(0, 0):
                return True
        return False

    # A provider may expose both a full timestamp and a time-only convenience
    # column. Prefer the full value so the trading date is never guessed.
    time_column = next(
        (candidate for candidate in time_candidates if _contains_full_timestamp(candidate)),
        time_candidates[0] if time_candidates else None,
    )
    price_column = _first_column(("price", "matchprice", "close", "last_price"))
    volume_column = _first_column(("volume", "matchvol", "vol", "quantity"))
    side_column = _first_column(("match_type", "side", "buysell", "type"))
    date_column = _first_column(
        tuple(
            candidate
            for candidate in ("tradingdate", "trading_date", "date", "tradingday", "trading_day")
            if candidate != time_column
        )
    )
    if time_column is None or price_column is None:
        return _IntradayFrameResult(
            pd.DataFrame(), error="thiếu cột thời gian hoặc giá khớp.", freshness="invalid"
        )

    parsed_times, time_error = _parse_intraday_times(
        frame[time_column],
        explicit_dates=frame[date_column] if date_column else None,
        fetched_at=fetched_at,
    )
    if parsed_times is None:
        return _IntradayFrameResult(
            pd.DataFrame(), error=time_error, freshness="ambiguous_date"
        )

    work = pd.DataFrame(index=frame.index)
    work["time"] = parsed_times
    work["price"] = pd.to_numeric(frame[price_column], errors="coerce")
    if volume_column:
        work["volume"] = pd.to_numeric(frame[volume_column], errors="coerce")
    if side_column:
        work["side"] = frame[side_column]
    work = work.dropna(subset=["time", "price"]).copy()
    work["time"] = pd.to_datetime(work["time"], utc=True).dt.tz_convert(VIETNAM_TZ)
    work = work[work["price"] > 0]
    if work.empty:
        return _IntradayFrameResult(
            pd.DataFrame(), error="dữ liệu khớp lệnh không đọc được.", freshness="invalid"
        )

    trading_dates = {stamp.date() for stamp in work["time"]}
    if len(trading_dates) != 1:
        return _IntradayFrameResult(
            pd.DataFrame(),
            error="dữ liệu chứa lệnh khớp từ nhiều ngày giao dịch.",
            freshness="session_mismatch",
        )
    trading_date = next(iter(trading_dates))

    local_clocks = [stamp.timetz().replace(tzinfo=None) for stamp in work["time"]]
    if any(
        clock < INTRADAY_SESSION_START or clock > INTRADAY_SESSION_END
        for clock in local_clocks
    ):
        return _IntradayFrameResult(
            pd.DataFrame(),
            error="thời điểm khớp nằm ngoài khung phiên giao dịch Việt Nam.",
            freshness="session_mismatch",
            trading_date=trading_date,
        )

    latest = max(work["time"])
    lag_seconds = float((fetched_at - latest).total_seconds())
    if trading_date > fetched_at.date() or lag_seconds < 0:
        return _IntradayFrameResult(
            pd.DataFrame(),
            error="thời điểm khớp nằm trong tương lai so với giờ Việt Nam của máy chủ.",
            freshness="future",
            trading_date=trading_date,
            lag_seconds=lag_seconds,
        )
    if trading_date < fetched_at.date():
        return _IntradayFrameResult(
            pd.DataFrame(),
            error=f"dữ liệu thuộc phiên cũ {trading_date.strftime('%d/%m/%Y')}.",
            freshness="stale",
            trading_date=trading_date,
            lag_seconds=lag_seconds,
        )
    if lag_seconds > max(0, int(max_lag_seconds)):
        return _IntradayFrameResult(
            pd.DataFrame(),
            error=(
                f"lệnh gần nhất đã chậm {lag_seconds / 60:.1f} phút; "
                "không dùng như dữ liệu trong phiên hiện tại."
            ),
            freshness="stale",
            trading_date=trading_date,
            lag_seconds=lag_seconds,
        )

    # MSN quotes equities in absolute VND; keep the nghìn-đồng convention.
    if source_name == "MSN" and symbol not in _INDEX_SYMBOLS:
        work["price"] = work["price"] / _MSN_PRICE_SCALE

    work = work.sort_values("time").reset_index(drop=True)
    work.attrs["symbol"] = symbol
    work.attrs["source"] = source_name
    work.attrs["fetched_at"] = fetched_at
    work.attrs["trading_date"] = trading_date.isoformat()
    work.attrs["freshness"] = "fresh"
    work.attrs["lag_seconds"] = lag_seconds
    return _IntradayFrameResult(
        work,
        freshness="fresh",
        trading_date=trading_date,
        lag_seconds=lag_seconds,
    )


def calculate_returns(prices_df):
    """Calculate aligned daily log returns from validated positive prices."""

    if not isinstance(prices_df, pd.DataFrame):
        raise DataQualityError(
            "Bảng giá (prices_df) phải là bảng dữ liệu pandas (DataFrame)."
        )
    if prices_df.empty:
        return pd.DataFrame(index=prices_df.index, columns=prices_df.columns, dtype=float)
    data = prices_df.copy()
    data = data.sort_index().loc[lambda df: ~df.index.duplicated(keep="last")]
    data = data.apply(pd.to_numeric, errors="coerce")
    data = data.where(data > 0)
    returns = np.log(data / data.shift(1))
    returns = returns.replace([np.inf, -np.inf], np.nan).dropna(how="any")
    if returns.empty:
        raise DataQualityError(
            "Không tính được lợi suất logarit hữu hạn đã căn chỉnh "
            "(aligned finite log returns)."
        )
    returns.attrs.update(prices_df.attrs)
    return returns
