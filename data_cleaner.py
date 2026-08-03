"""Bounded and validated import helpers for CSV/XLS/XLSX market data.

The public functions keep the original success contracts.  Invalid uploads now
raise ``UploadValidationError`` with a machine-readable code instead of feeding
unbounded or malformed content into pandas/openpyxl.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import io
import os
from pathlib import Path, PurePosixPath
import re
import zipfile
from typing import Any

import numpy as np
import pandas as pd


MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_XLSX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_ZIP_MEMBERS = 2_000
MAX_ZIP_RATIO = 100.0
MAX_SHEETS = 100
MAX_ROWS = 250_000
MAX_COLUMNS = 256
MAX_CELLS = 5_000_000
MAX_CELL_TEXT_LENGTH = 50_000

TICKER_RE = re.compile(r"^[A-Z]{2,5}$")
_SUPPORTED_EXTENSIONS = {".csv", ".xls", ".xlsx"}
_OLE_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")
_XML_FORBIDDEN = (b"<!doctype", b"<!entity")


@dataclass(frozen=True)
class UploadReport:
    """Facts established before a file is parsed."""

    filename: str
    extension: str
    size_bytes: int
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "details": dict(self.details),
        }


class UploadValidationError(ValueError):
    """A safe, structured upload/import failure."""

    def __init__(
        self, code: str, message: str, *, details: dict[str, Any] | None = None
    ) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "details": dict(self.details),
        }


def _filename(file_like: Any) -> str:
    name = getattr(file_like, "name", None)
    if name is None and isinstance(file_like, (str, os.PathLike)):
        name = os.fspath(file_like)
    return Path(str(name or "upload")).name


def _extension(file_like: Any) -> str:
    return Path(_filename(file_like)).suffix.lower()


def _read_bounded_bytes(file_like: Any) -> bytes:
    """Read at most the accepted upload size while preserving stream position."""

    if isinstance(file_like, (str, os.PathLike)):
        path = Path(file_like)
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise UploadValidationError(
                "FILE_UNREADABLE", "Không thể đọc tệp đã chọn."
            ) from exc
        if size > MAX_UPLOAD_BYTES:
            raise UploadValidationError(
                "FILE_TOO_LARGE",
                f"Tệp vượt giới hạn {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB.",
                details={"size_bytes": size, "maximum_bytes": MAX_UPLOAD_BYTES},
            )
        try:
            return path.read_bytes()
        except OSError as exc:
            raise UploadValidationError(
                "FILE_UNREADABLE", "Không thể đọc tệp đã chọn."
            ) from exc

    if not hasattr(file_like, "read"):
        raise UploadValidationError(
            "INVALID_FILE_OBJECT", "Đầu vào không phải tệp hoặc luồng có thể đọc."
        )
    position = None
    try:
        if hasattr(file_like, "tell"):
            position = file_like.tell()
        if hasattr(file_like, "seek"):
            file_like.seek(0)
        payload = file_like.read(MAX_UPLOAD_BYTES + 1)
    except Exception as exc:
        raise UploadValidationError(
            "FILE_UNREADABLE", "Không thể đọc nội dung tệp đã chọn."
        ) from exc
    finally:
        if position is not None and hasattr(file_like, "seek"):
            try:
                file_like.seek(position)
            except Exception:
                pass
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise UploadValidationError(
            "INVALID_FILE_OBJECT", "Luồng tệp không trả về dữ liệu nhị phân hợp lệ."
        )
    payload = bytes(payload)
    if len(payload) > MAX_UPLOAD_BYTES:
        raise UploadValidationError(
            "FILE_TOO_LARGE",
            f"Tệp vượt giới hạn {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB.",
            details={
                "size_bytes_at_least": len(payload),
                "maximum_bytes": MAX_UPLOAD_BYTES,
            },
        )
    return payload


def _scan_xml_stream(member: Any) -> None:
    carry = b""
    while True:
        chunk = member.read(64 * 1024)
        if not chunk:
            return
        sample = (carry + chunk).lower()
        if any(token in sample for token in _XML_FORBIDDEN):
            raise UploadValidationError(
                "UNSAFE_XML",
                "Tệp Excel chứa khai báo DTD/entity không được hỗ trợ.",
            )
        carry = sample[-16:]


def _validate_xlsx(payload: bytes) -> dict[str, Any]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except (OSError, zipfile.BadZipFile) as exc:
        raise UploadValidationError(
            "INVALID_XLSX", "Tệp .xlsx không phải gói Office ZIP hợp lệ."
        ) from exc
    with archive:
        members = archive.infolist()
        if len(members) > MAX_ZIP_MEMBERS:
            raise UploadValidationError(
                "TOO_MANY_ARCHIVE_ENTRIES",
                "Tệp Excel chứa quá nhiều thành phần nén.",
                details={"entries": len(members), "maximum": MAX_ZIP_MEMBERS},
            )
        total_uncompressed = 0
        total_compressed = 0
        names: set[str] = set()
        for info in members:
            normalised = info.filename.replace("\\", "/")
            path = PurePosixPath(normalised)
            if normalised.startswith("/") or ".." in path.parts:
                raise UploadValidationError(
                    "UNSAFE_ARCHIVE_PATH",
                    "Tệp Excel chứa đường dẫn thành phần không an toàn.",
                )
            if info.flag_bits & 0x1:
                raise UploadValidationError(
                    "ENCRYPTED_ARCHIVE",
                    "Tệp Excel được mã hóa nên không thể kiểm tra an toàn.",
                )
            names.add(normalised.lower())
            total_uncompressed += int(info.file_size)
            total_compressed += int(info.compress_size)
        if total_uncompressed > MAX_XLSX_UNCOMPRESSED_BYTES:
            raise UploadValidationError(
                "ARCHIVE_TOO_LARGE",
                "Dung lượng giải nén của tệp Excel vượt giới hạn an toàn.",
                details={
                    "uncompressed_bytes": total_uncompressed,
                    "maximum_bytes": MAX_XLSX_UNCOMPRESSED_BYTES,
                },
            )
        ratio = total_uncompressed / max(1, total_compressed)
        if ratio > MAX_ZIP_RATIO:
            raise UploadValidationError(
                "SUSPICIOUS_COMPRESSION_RATIO",
                "Tỷ lệ nén của tệp Excel vượt giới hạn an toàn.",
                details={"ratio": ratio, "maximum": MAX_ZIP_RATIO},
            )
        required = {"[content_types].xml", "xl/workbook.xml"}
        if not required.issubset(names):
            raise UploadValidationError(
                "INVALID_XLSX_STRUCTURE",
                "Tệp .xlsx thiếu cấu trúc workbook bắt buộc.",
            )
        for info in members:
            if info.filename.lower().endswith((".xml", ".rels")):
                try:
                    with archive.open(info, "r") as member:
                        _scan_xml_stream(member)
                except UploadValidationError:
                    raise
                except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                    raise UploadValidationError(
                        "INVALID_XLSX", "Không thể kiểm tra thành phần XML của tệp."
                    ) from exc
    return {
        "archive_entries": len(members),
        "uncompressed_bytes": total_uncompressed,
        "compression_ratio": ratio,
    }


def _validate_csv(payload: bytes) -> dict[str, Any]:
    if not payload:
        raise UploadValidationError("EMPTY_FILE", "Tệp CSV rỗng.")
    utf16 = payload.startswith((b"\xff\xfe", b"\xfe\xff"))
    if not utf16 and b"\x00" in payload:
        raise UploadValidationError(
            "BINARY_CONTENT", "Tệp .csv chứa byte NUL giống dữ liệu nhị phân."
        )
    sample = payload[: min(len(payload), 64 * 1024)]
    if not utf16:
        controls = sum(
            1 for value in sample if value < 32 and value not in (9, 10, 13)
        )
        if sample and controls / len(sample) > 0.02:
            raise UploadValidationError(
                "BINARY_CONTENT", "Nội dung tệp không giống dữ liệu CSV văn bản."
            )
    return {"encoding_hint": "utf-16" if utf16 else "text"}


def validate_upload(file_like: Any) -> UploadReport:
    """Validate type, magic bytes, size, and archive safety before parsing."""

    filename = _filename(file_like)
    extension = _extension(file_like)
    if extension not in _SUPPORTED_EXTENSIONS:
        raise UploadValidationError(
            "UNSUPPORTED_FILE_TYPE",
            "Chỉ hỗ trợ tệp .csv, .xls hoặc .xlsx.",
            details={"extension": extension or None},
        )
    payload = _read_bounded_bytes(file_like)
    if not payload:
        raise UploadValidationError("EMPTY_FILE", "Tệp tải lên rỗng.")
    if extension == ".xlsx":
        if not payload.startswith(b"PK"):
            raise UploadValidationError(
                "FILE_SIGNATURE_MISMATCH",
                "Phần mở rộng .xlsx không khớp nội dung tệp.",
            )
        details = _validate_xlsx(payload)
    elif extension == ".xls":
        if not payload.startswith(_OLE_MAGIC):
            raise UploadValidationError(
                "FILE_SIGNATURE_MISMATCH",
                "Phần mở rộng .xls không khớp nội dung tệp OLE.",
            )
        details = {"container": "OLE"}
    else:
        details = _validate_csv(payload)
    return UploadReport(
        filename=filename,
        extension=extension,
        size_bytes=len(payload),
        details=details,
    )


def _rewind(file_like: Any) -> None:
    if not isinstance(file_like, (str, os.PathLike)) and hasattr(file_like, "seek"):
        try:
            file_like.seek(0)
        except Exception as exc:
            raise UploadValidationError(
                "FILE_UNREADABLE", "Không thể tua lại luồng tệp để đọc."
            ) from exc


def _validate_frame(frame: Any, *, context: str = "dữ liệu") -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise UploadValidationError(
            "INVALID_TABLE", f"{context.capitalize()} không phải bảng hai chiều."
        )
    rows, columns = frame.shape
    if rows == 0 or columns == 0:
        raise UploadValidationError("EMPTY_TABLE", f"{context.capitalize()} không có dữ liệu.")
    if rows > MAX_ROWS or columns > MAX_COLUMNS or rows * columns > MAX_CELLS:
        raise UploadValidationError(
            "TABLE_TOO_LARGE",
            f"{context.capitalize()} vượt giới hạn hàng, cột hoặc tổng số ô.",
            details={
                "rows": rows,
                "columns": columns,
                "cells": rows * columns,
                "maximum_rows": MAX_ROWS,
                "maximum_columns": MAX_COLUMNS,
                "maximum_cells": MAX_CELLS,
            },
        )
    for column in frame.select_dtypes(include=["object", "string"]).columns:
        values = frame[column].dropna()
        if values.empty:
            continue
        longest = int(values.astype(str).str.len().max())
        if longest > MAX_CELL_TEXT_LENGTH:
            raise UploadValidationError(
                "CELL_TEXT_TOO_LONG",
                "Một ô văn bản vượt giới hạn độ dài an toàn.",
                details={
                    "column": str(column),
                    "length": longest,
                    "maximum": MAX_CELL_TEXT_LENGTH,
                },
            )
    return frame


def list_sheets(file_like: Any, *, strict: bool = False) -> list[str]:
    """Return Excel sheet names; CSV returns ``[]``.

    ``strict=False`` preserves the historical UI contract (sheet discovery is
    advisory and returns ``[]`` on an invalid workbook).  Set ``strict=True``
    to receive ``UploadValidationError`` immediately.  ``read_raw`` and
    ``smart_import`` always validate strictly before parsing.
    """

    try:
        report = validate_upload(file_like)
        if report.extension == ".csv":
            return []
        _rewind(file_like)
        with pd.ExcelFile(file_like) as workbook:
            sheets = list(map(str, workbook.sheet_names))
        if not sheets:
            raise UploadValidationError("NO_SHEETS", "Workbook không có sheet dữ liệu.")
        if len(sheets) > MAX_SHEETS:
            raise UploadValidationError(
                "TOO_MANY_SHEETS",
                "Workbook chứa quá nhiều sheet.",
                details={"sheets": len(sheets), "maximum": MAX_SHEETS},
            )
        return sheets
    except UploadValidationError:
        if strict:
            raise
        return []
    except Exception as exc:
        if strict:
            raise UploadValidationError(
                "WORKBOOK_PARSE_ERROR", "Không thể đọc danh sách sheet của workbook."
            ) from exc
        return []
    finally:
        try:
            _rewind(file_like)
        except UploadValidationError:
            pass


def read_raw(file_like: Any, sheet: str | int | None = None, header: int | None = 0):
    """Strictly validate and parse one sheet (or a CSV) with bounded output."""

    if header is not None and (not isinstance(header, int) or not 0 <= header <= 100):
        raise UploadValidationError(
            "INVALID_HEADER", "Dòng tiêu đề phải từ 0 đến 100 hoặc để trống."
        )
    report = validate_upload(file_like)
    _rewind(file_like)
    try:
        if report.extension == ".csv":
            parsed = pd.read_csv(file_like, header=header)
        else:
            parsed = pd.read_excel(file_like, sheet_name=sheet, header=header)
    except UploadValidationError:
        raise
    except Exception as exc:
        raise UploadValidationError(
            "TABLE_PARSE_ERROR",
            "Không thể phân tích nội dung tệp dữ liệu.",
            details={"exception_type": type(exc).__name__},
        ) from exc
    finally:
        _rewind(file_like)
    if isinstance(parsed, dict):
        if not parsed:
            raise UploadValidationError("NO_SHEETS", "Workbook không có sheet dữ liệu.")
        if len(parsed) > MAX_SHEETS:
            raise UploadValidationError(
                "TOO_MANY_SHEETS", "Workbook chứa quá nhiều sheet."
            )
        return {
            str(name): _validate_frame(frame, context=f"sheet {name}")
            for name, frame in parsed.items()
        }
    return _validate_frame(parsed)


def _frac(series: pd.Series, predicate: Any) -> float:
    values = series.dropna()
    if len(values) == 0:
        return 0.0
    return float(np.mean([bool(predicate(value)) for value in values]))


def _is_date_val(value: Any) -> bool:
    try:
        integer = int(value)
    except (ValueError, TypeError, OverflowError):
        return False
    return 19000101 <= integer <= 21001231


def _is_ticker_val(value: Any) -> bool:
    return isinstance(value, str) and bool(TICKER_RE.fullmatch(value.strip()))


def _is_number_val(value: Any) -> bool:
    return isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(
        value, (bool, np.bool_)
    ) and bool(np.isfinite(value))


def classify_columns(raw: pd.DataFrame) -> list[str]:
    """Classify each column as date, ticker, price, volume, or other."""

    _validate_frame(raw)
    kinds: list[str] = []
    for index in range(raw.shape[1]):
        column = raw.iloc[:, index]
        if _frac(column, _is_date_val) > 0.6:
            kinds.append("date")
        elif _frac(column, _is_ticker_val) > 0.6:
            kinds.append("ticker")
        elif _frac(column, _is_number_val) > 0.6:
            numbers = [value for value in column.dropna() if _is_number_val(value)]
            big = np.mean([abs(value) > 100_000 for value in numbers]) if numbers else 0
            kinds.append("volume" if big > 0.6 else "price")
        else:
            kinds.append("other")
    return kinds


def extract_price_blocks(raw: pd.DataFrame):
    """Convert repeated Ticker/Date/Close blocks into one aligned price table."""

    kinds = classify_columns(raw)
    number_of_columns = raw.shape[1]
    series_map: dict[str, pd.Series] = {}
    used_names: set[str] = set()
    report_lines: list[str] = []

    for index in range(number_of_columns):
        if kinds[index] != "ticker":
            continue
        column = raw.iloc[:, index]
        symbols = [value.strip() for value in column.dropna() if _is_ticker_val(value)]
        if not symbols:
            continue
        symbol = pd.Series(symbols).mode().iloc[0]

        price_index = next(
            (
                candidate
                for candidate in range(index + 1, min(index + 4, number_of_columns))
                if kinds[candidate] == "price"
            ),
            None,
        )
        if price_index is None:
            continue

        date_index = next(
            (
                candidate
                for candidate in range(index + 1, min(index + 4, number_of_columns))
                if kinds[candidate] == "date"
            ),
            None,
        )
        if date_index is None:
            date_index = next(
                (
                    candidate
                    for candidate in range(index - 1, max(index - 4, -1), -1)
                    if kinds[candidate] == "date"
                ),
                None,
            )

        price = pd.to_numeric(raw.iloc[:, price_index], errors="coerce")
        price = price.where(np.isfinite(price) & price.gt(0))
        if date_index is not None:
            dates = pd.to_numeric(raw.iloc[:, date_index], errors="coerce")
            series = pd.DataFrame({"date": dates, "price": price}).dropna()
            series = series.drop_duplicates("date", keep="last").set_index("date")["price"]
            series.index = series.index.astype("int64")
        else:
            series = price.dropna().reset_index(drop=True)
        if series.empty:
            continue

        name = symbol
        suffix = 2
        while name in used_names:
            name = f"{symbol}_{suffix}"
            suffix += 1
        used_names.add(name)
        series_map[name] = series
        report_lines.append(f"{name}: {len(series)} dòng giá")

    if len(series_map) < 2:
        return None, "Không nhận diện được định dạng khối cổ phiếu."
    tidy = pd.DataFrame(series_map).sort_index()
    tidy.index.name = "Ngày"
    tidy = _validate_frame(tidy.reset_index(), context="bảng giá đã tách")
    report = f"Đã tách {len(series_map)} mã: " + ", ".join(report_lines)
    return tidy, report


def clean_generic(raw: pd.DataFrame) -> pd.DataFrame:
    """Drop blank axes, normalise names, and safely infer numeric columns."""

    _validate_frame(raw)
    frame = raw.copy().dropna(axis=1, how="all").dropna(axis=0, how="all")
    if frame.empty or frame.shape[1] == 0:
        raise UploadValidationError(
            "EMPTY_TABLE_AFTER_CLEANING", "Không còn dữ liệu sau khi bỏ hàng/cột rỗng."
        )
    new_columns: list[str] = []
    seen: dict[str, int] = {}
    for column in frame.columns:
        name = str(column).strip() or "column"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        new_columns.append(name)
    frame.columns = new_columns
    for column in frame.columns:
        converted = pd.to_numeric(frame[column], errors="coerce")
        if converted.notna().mean() > 0.7:
            frame[column] = converted.replace([np.inf, -np.inf], np.nan)
    return _validate_frame(frame, context="dữ liệu đã làm sạch")


def smart_import(file_like: Any, sheet: str | int | None = None, mode: str = "auto"):
    """Import a validated table, preserving the original ``(df, report)`` API."""

    if mode not in {"auto", "raw"}:
        raise UploadValidationError(
            "INVALID_IMPORT_MODE", "Chế độ nhập phải là 'auto' hoặc 'raw'."
        )
    raw = read_raw(file_like, sheet=sheet, header=0)
    if isinstance(raw, dict):
        raw = next(iter(raw.values()))
    if mode == "raw":
        return raw, "Đọc nguyên bản (đã kiểm tra an toàn đầu vào)."

    tidy, report = extract_price_blocks(raw)
    if tidy is not None:
        return tidy, "🧠 Nhận diện định dạng khối cổ phiếu. " + report
    cleaned = clean_generic(raw)
    return (
        cleaned,
        "🧹 Đã làm sạch cơ bản (bỏ cột/dòng rỗng, chuẩn hoá tên cột, ép kiểu số).",
    )
