"""Kiểm thử bộ công cụ thống kê phổ thông (lớp 10–12).

Phần tính toán phải khớp phép tính tay theo SGK Kết nối tri thức; phần hiển thị
chỉ cần dựng nổi bằng Streamlit AppTest và không được ném ngoại lệ.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import stats_tools as stt


SAMPLE = [-2.0, 1.0, 0.5, 3.0, -1.0]


# ---------------------------------------------------------------------------
# Số gần đúng và sai số (s1)
# ---------------------------------------------------------------------------

def test_approx_error_absolute_and_relative():
    err = stt.approx_error(25.5, 25.0)
    assert err["abs_error"] == pytest.approx(0.5)
    assert err["rel_error_pct"] == pytest.approx(2.0)


def test_approx_error_is_absolute_in_value():
    assert stt.approx_error(24.8, 25.0)["abs_error"] == pytest.approx(0.2)


def test_approx_error_zero_reference_gives_nan_relative():
    assert math.isnan(stt.approx_error(1.0, 0.0)["rel_error_pct"])


# ---------------------------------------------------------------------------
# Đọc số liệu nhập tay
# ---------------------------------------------------------------------------

def test_parse_values_accepts_common_separators():
    assert stt.parse_values("-2, 1; 0.5\n3\t-1") == [-2.0, 1.0, 0.5, 3.0, -1.0]


def test_parse_values_strips_percent_signs_and_junk():
    assert stt.parse_values("1.5%, abc, -0.25%") == [1.5, -0.25]


def test_parse_values_empty_raises():
    with pytest.raises(ValueError):
        stt.parse_values("hai, ba")


# ---------------------------------------------------------------------------
# Số đặc trưng không ghép nhóm (s2)
# ---------------------------------------------------------------------------

def test_summary_centre_matches_hand_calculation():
    s = stt.summarize_ungrouped(SAMPLE)
    assert s["n"] == 5
    assert s["mean"] == pytest.approx(0.3)
    assert s["median"] == pytest.approx(0.5)


def test_summary_dispersion_matches_textbook_example():
    s = stt.summarize_ungrouped(SAMPLE)
    assert s["variance"] == pytest.approx(2.96)
    assert s["std"] == pytest.approx(1.7205, abs=0.001)


def test_summary_quartiles_range_and_mode():
    s = stt.summarize_ungrouped(SAMPLE)
    assert s["range"] == pytest.approx(5.0)
    # Ma sı xếp: (−2; −1; 0,5; 1; 3) — trung vị 0,5 không thuộc nửa trái/phải.
    assert s["q1"] == pytest.approx(-1.5)
    assert s["q3"] == pytest.approx(2.0)
    assert s["iqr"] == pytest.approx(3.5)
    assert s["modes"] == ()


def test_an_and_binh_share_mean_but_not_spread():
    an = [9.2, 8.7, 9.5, 6.8, 8.0, 8.0, 7.3, 6.5]
    binh = [8.2, 8.1, 8.0, 7.8, 8.3, 7.9, 7.6, 8.1]
    sa, sb = stt.summarize_ungrouped(an), stt.summarize_ungrouped(binh)
    assert sa["mean"] == pytest.approx(8.0)
    assert sb["mean"] == pytest.approx(8.0)
    assert sa["variance"] == pytest.approx(1.045)
    assert sb["variance"] == pytest.approx(0.045)
    assert sb["std"] < sa["std"]


def test_outliers_detected_by_15_iqr_rule():
    s = stt.summarize_ungrouped([-5.0, 1.0, 1.5, 2.0, 2.5, 3.0, 100.0])
    assert -5.0 in s["outliers"]
    assert 100.0 in s["outliers"]


def test_constant_sample_reports_no_outliers():
    s = stt.summarize_ungrouped([2.0, 2.0, 2.0, 2.0])
    assert s["iqr"] == 0
    assert not s["outliers"]


def test_summary_needs_at_least_two_values():
    with pytest.raises(ValueError):
        stt.summarize_ungrouped([1.0])


# ---------------------------------------------------------------------------
# Ghép nhóm (s3) và phân tán ghép nhóm (s4)
# ---------------------------------------------------------------------------

def test_group_series_evenly_spaced_boundaries():
    groups = stt.group_series(list(range(10)), 5)
    assert groups["boundaries"][0] == pytest.approx(0.0)
    assert groups["boundaries"][-1] == pytest.approx(9.0)
    assert len(groups["counts"]) == 5
    assert sum(groups["counts"]) == 10
    # Mỗi nhóm rộng 9/5 = 1,8; nhóm đầu có tâm (0 + 1,8)/2 = 0,9.
    assert groups["mids"][0] == pytest.approx(0.9)


def test_grouped_stats_hand_calculation():
    # Dãy 0..9, k = 5: nhóm rộng 1,8, tần số đều là 2, đại diện 0,9; 2,7; 4,5; 6,3; 8,1.
    groups = stt.group_series(list(range(10)), 5)
    assert groups["mids"] == pytest.approx([0.9, 2.7, 4.5, 6.3, 8.1])
    g = stt.summarize_grouped(list(range(10)), 5)
    assert g["mean"] == pytest.approx(4.5)
    assert g["variance"] == pytest.approx(6.48)
    assert g["std"] == pytest.approx(math.sqrt(6.48))
    # N/4 = 2,5 chạm giữa nhóm thứ hai [1,8; 3,6): Q1 = 1,8 + (0,5/2)·1,8 = 2,25.
    assert g["q1"] == pytest.approx(2.25)
    assert g["q3"] == pytest.approx(6.75)
    assert g["iqr"] == pytest.approx(4.5)
    assert g["range"] == pytest.approx(9.0)


def test_grouped_median_interpolates_within_group():
    # Dãy 0..9: N/2 = 5 nằm giữa nhóm [3,6; 5,4) có tâm 4,5.
    assert stt.summarize_grouped(list(range(10)), 5)["median"] == pytest.approx(4.5)


def test_compare_grouping_reports_relative_error():
    _, _, table = stt.compare_grouping(SAMPLE, 2)
    mean_row = table.iloc[0]
    assert mean_row["Không ghép nhóm"] == pytest.approx(0.3)
    assert mean_row["Ghép nhóm (ước lượng)"] == pytest.approx(0.75)
    assert mean_row["Sai số tương đối (%)"] == pytest.approx(150.0)


# ---------------------------------------------------------------------------
# Bảng tần suất hai chiều và lợi suất (tổ chức dữ liệu)
# ---------------------------------------------------------------------------

def test_updown_tally_counts_by_symbol():
    prices = pd.DataFrame({"A": [1, 2, 2, 1], "VNINDEX": [1, 1, 1, 1]})
    tally = stt.updown_tally(prices, ["A", "VNINDEX"])
    row_a = tally.loc[tally["Mã"] == "A"].iloc[0]
    assert row_a["Tăng"] == 1
    assert row_a["Giảm"] == 1
    assert row_a["Không đổi"] == 1
    assert row_a["Số phiên"] == 3
    row_index = tally.loc[tally["Mã"] == "VNINDEX"].iloc[0]
    assert row_index["Không đổi"] == 3


def test_pct_returns_percentage_and_tail():
    prices = pd.DataFrame({"A": [100.0, 101.0, 99.0]})
    returns = stt.pct_returns(prices, "A", 1)
    assert len(returns) == 1
    assert returns.iloc[-1] == pytest.approx((99.0 / 101.0 - 1.0) * 100.0)


# ---------------------------------------------------------------------------
# Ba công cụ hiển thị phải dựng nổi được
# ---------------------------------------------------------------------------

def test_render_stats_calculator_smoke():
    at = AppTest.from_string(
        "import stats_tools as stt, sample_data as sd\n"
        "stt.render_stats_calculator(sd.make_sample_prices(), 'VNINDEX')",
        default_timeout=60,
    ).run()
    assert not at.exception


def test_render_grouping_lab_smoke():
    at = AppTest.from_string(
        "import stats_tools as stt, sample_data as sd\n"
        "stt.render_grouping_lab(sd.make_sample_prices(), 'VNINDEX')",
        default_timeout=60,
    ).run()
    assert not at.exception


def test_render_frequency_table_with_no_data_falls_back_to_demo():
    at = AppTest.from_string(
        "import pandas as pd\nimport stats_tools as stt\n"
        "stt.render_frequency_table(pd.DataFrame(), 'VNINDEX')",
        default_timeout=60,
    ).run()
    assert not at.exception
    assert any("mô phỏng" in i.value for i in at.info)
