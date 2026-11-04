"""Nhận xét EViews phải nói đúng ý nghĩa và đúng nhánh chẩn đoán.

Dữ liệu VIC/REE/STB/VNINDEX là 150 quan sát trong fixtures, cùng bộ số đã đối chiếu
với EViews 4 ở test_eviews_parity.py. Các ca tổng hợp dựng sẵn để kích hoạt từng nhánh.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import eviews_emulator as ev
from eviews_commentary import commentary_for


@pytest.fixture(scope="module")
def data():
    df = pd.read_csv(Path(__file__).parent / "fixtures" / "eviews_parity_150.csv")
    for name in ("VIC", "REE", "STB", "VNINDEX"):
        df = ev.parse_and_execute_command(f"GENR R_{name} = LOG({name})-LOG({name}(-1))", df)["data"]
    return df


def _synthetic(columns):
    return pd.DataFrame(columns)


def test_returns_regression_explains_beta_r2_and_alpha(data):
    text = commentary_for(ev.parse_and_execute_command("LS(H) R_VIC C R_VNINDEX", data))
    assert "β = 0.959152" in text
    assert "khi R_VNINDEX tăng 1% thì R_VIC thay đổi trung bình 0.96%" in text
    assert "p = 0.8317" in text  # β = 1 không bị bác bỏ
    assert "chưa đủ bằng chứng để nói nhạy hơn hay ít nhạy hơn" in text
    assert "23.3% biến động của R_VIC" in text
    assert "SE White (HC1) = 0.191825 (SE thường = 0.143669; bạn đã chọn LS(H))" in text
    assert "dùng được, vì các chuỗi đều dừng" in text
    assert "Không ra quyết định từ β, C hay R²" not in text


def test_price_level_regression_is_flagged_and_decisions_are_withheld(data):
    text = commentary_for(ev.parse_and_execute_command("LS VIC C VNINDEX", data))
    assert "Không ra quyết định từ β, C hay R² của mô hình này" in text
    assert "có chuỗi không dừng (VIC, VNINDEX)" in text
    assert "Không phân loại và không ra quyết định từ β" in text
    assert "năng động" not in text
    assert "phòng thủ" not in text
    assert "lợi suất vượt trội" in text  # nói rõ là không dùng C để kết luận


def test_adf_reports_stationary_and_nonstationary_series(data):
    stationary = commentary_for(ev.parse_and_execute_command("ADF R_VIC", data))
    assert "R_VIC là chuỗi dừng" in stationary
    levels = commentary_for(ev.parse_and_execute_command("ADF VIC", data))
    assert "VIC có thể không dừng" in levels
    assert "hồi quy giả mạo" in levels


def test_reset_failure_is_reported_as_wrong_functional_form():
    rng = np.random.default_rng(3)
    x = rng.uniform(-1, 1, 200)
    y = x ** 2 + rng.normal(scale=0.05, size=200)
    df = _synthetic({"Y": y, "X": x})
    text = commentary_for(ev.parse_and_execute_command("LS Y C X", df))
    assert "Dạng hàm chưa phù hợp" in text
    assert "Dạng hàm (RESET):** p < 0.0001" in text


def test_autocorrelated_residuals_are_reported():
    rng = np.random.default_rng(5)
    n = 300
    e = np.zeros(n)
    for t in range(1, n):
        e[t] = 0.8 * e[t - 1] + rng.normal()
    x = rng.normal(size=n)
    y = 0.5 * x + e
    df = _synthetic({"Y": y, "X": x})
    text = commentary_for(ev.parse_and_execute_command("LS Y C X", df))
    assert "Có tự tương quan" in text
    assert "Tự tương quan (Breusch–Godfrey):** p < 0.0001" in text


def test_fat_tailed_residuals_are_reported_with_var_warning():
    rng = np.random.default_rng(11)
    n = 300
    x = rng.normal(size=n)
    y = 0.3 * x + rng.standard_t(df=3, size=n)
    df = _synthetic({"Y": y, "X": x})
    text = commentary_for(ev.parse_and_execute_command("LS Y C X", df))
    assert "Nghĩa là sai số lệch hoặc có đuôi dày" in text
    assert "đánh giá thấp tổn thất cực đoan" in text


def test_collinear_regressors_are_flagged_by_vif():
    rng = np.random.default_rng(7)
    n = 200
    x1 = rng.normal(size=n)
    x2 = x1 + rng.normal(scale=0.01, size=n)
    y = 0.4 * x1 + rng.normal(size=n)
    df = _synthetic({"Y": y, "X1": x1, "X2": x2})
    text = commentary_for(ev.parse_and_execute_command("LS Y C X1 X2", df))
    assert "Đa cộng tuyến (VIF):** X1 = " in text
    vif_x1 = float(re.search(r"X1 = ([0-9.]+)", text).group(1))
    assert vif_x1 > 10
    assert "VIF trên 10 là nặng" in text


def test_small_sample_is_marked_as_indicative():
    rng = np.random.default_rng(2)
    df = _synthetic({"Y": rng.normal(size=20), "X": rng.normal(size=20)})
    text = commentary_for(ev.parse_and_execute_command("LS Y C X", df))
    assert "Mẫu nhỏ (20 quan sát)" in text


def test_commentary_is_none_for_errors_and_unknown_results():
    assert commentary_for({"error": "Lệnh chưa hỗ trợ."}) is None
    assert commentary_for({"message": "Đã tạo biến."}) is None
    assert commentary_for("không phải dict") is None
