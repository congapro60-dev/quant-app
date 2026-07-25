"""
Module nhập liệu thông minh cho Quant App.
Xử lý các file Excel/CSV lộn xộn: chọn sheet, dò dòng tiêu đề,
nhận diện cột số, và tách định dạng "khối" (Ticker/Date/Close lặp lại)
thành bảng giá gọn gàng (mỗi mã 1 cột, index theo ngày).
"""
import re
import numpy as np
import pandas as pd

TICKER_RE = re.compile(r'^[A-Z]{2,5}$')


def list_sheets(file_like):
    """Trả về danh sách tên sheet của file Excel. CSV trả về []."""
    name = getattr(file_like, 'name', str(file_like))
    if name.lower().endswith('.csv'):
        return []
    try:
        xls = pd.ExcelFile(file_like)
        return xls.sheet_names
    except Exception:
        return []


def read_raw(file_like, sheet=None, header=0):
    """Đọc thô một sheet (hoặc CSV) không suy diễn nhiều."""
    name = getattr(file_like, 'name', str(file_like))
    if name.lower().endswith('.csv'):
        return pd.read_csv(file_like, header=header)
    return pd.read_excel(file_like, sheet_name=sheet, header=header)


def _frac(series, pred):
    vals = series.dropna()
    if len(vals) == 0:
        return 0.0
    return float(np.mean([bool(pred(v)) for v in vals]))


def _is_date_val(v):
    try:
        iv = int(v)
    except (ValueError, TypeError):
        return False
    return 19000101 <= iv <= 21001231


def _is_ticker_val(v):
    return isinstance(v, str) and bool(TICKER_RE.match(v.strip()))


def _is_number_val(v):
    return isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool)


def classify_columns(raw):
    """Phân loại từng cột: date / ticker / price / volume / other."""
    kinds = []
    for i in range(raw.shape[1]):
        col = raw.iloc[:, i]
        if _frac(col, _is_date_val) > 0.6:
            kinds.append('date')
        elif _frac(col, _is_ticker_val) > 0.6:
            kinds.append('ticker')
        elif _frac(col, _is_number_val) > 0.6:
            # Phân biệt volume (số nguyên rất lớn) với giá
            nums = [v for v in col.dropna() if _is_number_val(v)]
            big = np.mean([abs(v) > 100000 for v in nums]) if nums else 0
            kinds.append('volume' if big > 0.6 else 'price')
        else:
            kinds.append('other')
    return kinds


def extract_price_blocks(raw):
    """
    Tách định dạng khối lặp <Ticker>/<Date>/<Close> thành bảng giá gọn.
    Trả về (df_tidy, report) hoặc (None, report) nếu không nhận diện được.
    """
    kinds = classify_columns(raw)
    ncol = raw.shape[1]
    series_map = {}
    used_names = set()
    report_lines = []

    for i in range(ncol):
        if kinds[i] != 'ticker':
            continue
        col = raw.iloc[:, i]
        symbols = [v.strip() for v in col.dropna() if _is_ticker_val(v)]
        if not symbols:
            continue
        symbol = pd.Series(symbols).mode().iloc[0]

        # Tìm cột giá gần nhất bên phải (trong 3 cột)
        price_idx = None
        for j in range(i + 1, min(i + 4, ncol)):
            if kinds[j] == 'price':
                price_idx = j
                break
        if price_idx is None:
            continue

        # Tìm cột ngày gần nhất (ưu tiên bên phải, rồi bên trái)
        date_idx = None
        for j in range(i + 1, min(i + 4, ncol)):
            if kinds[j] == 'date':
                date_idx = j
                break
        if date_idx is None:
            for j in range(i - 1, max(i - 4, -1), -1):
                if kinds[j] == 'date':
                    date_idx = j
                    break

        price = pd.to_numeric(raw.iloc[:, price_idx], errors='coerce')
        if date_idx is not None:
            dates = pd.to_numeric(raw.iloc[:, date_idx], errors='coerce')
            s = pd.DataFrame({'d': dates, 'p': price}).dropna()
            s = s.drop_duplicates('d').set_index('d')['p']
            s.index = s.index.astype('int64')
        else:
            s = price.dropna().reset_index(drop=True)

        name = symbol
        k = 2
        while name in used_names:
            name = f"{symbol}_{k}"
            k += 1
        used_names.add(name)
        series_map[name] = s
        report_lines.append(f"{name}: {len(s)} dòng giá")

    if len(series_map) < 2:
        return None, "Không nhận diện được định dạng khối cổ phiếu."

    tidy = pd.DataFrame(series_map).sort_index()
    tidy.index.name = 'Ngày'
    tidy = tidy.reset_index()
    report = f"Đã tách {len(series_map)} mã: " + ", ".join(report_lines)
    return tidy, report


def clean_generic(raw):
    """Làm sạch cơ bản: bỏ dòng/cột rỗng, chuẩn hoá tên cột, ép kiểu số."""
    df = raw.copy()
    df = df.dropna(axis=1, how='all').dropna(axis=0, how='all')
    # Chuẩn hoá tên cột
    new_cols, seen = [], {}
    for c in df.columns:
        name = str(c).strip()
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        new_cols.append(name)
    df.columns = new_cols
    # Ép kiểu số nơi có thể
    for c in df.columns:
        conv = pd.to_numeric(df[c], errors='coerce')
        if conv.notna().mean() > 0.7:
            df[c] = conv
    return df


def smart_import(file_like, sheet=None, mode='auto'):
    """
    Nhập liệu thông minh.
    mode='auto': thử tách khối cổ phiếu -> nếu không được thì làm sạch cơ bản.
    mode='raw': đọc nguyên bản.
    Trả về (df, report).
    """
    raw = read_raw(file_like, sheet=sheet, header=0)
    if isinstance(raw, dict):  # phòng khi sheet_name=None
        raw = list(raw.values())[0]

    if mode == 'raw':
        return raw, "Đọc nguyên bản (không xử lý)."

    tidy, rep = extract_price_blocks(raw)
    if tidy is not None:
        return tidy, "🧠 Nhận diện định dạng khối cổ phiếu. " + rep

    cleaned = clean_generic(raw)
    return cleaned, "🧹 Đã làm sạch cơ bản (bỏ cột/dòng rỗng, chuẩn hoá tên cột, ép kiểu số)."
