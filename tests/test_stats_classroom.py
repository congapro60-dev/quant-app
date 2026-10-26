"""Kiểm thử Phòng học thống kê: khóa số giáo án, registry phòng, exit ticket.

Số liệu kịch bản đã kiểm chứng bằng Python và khớp giáo án 100% (Toán 10
B13–B14; Toán 11 cổ phiếu ghép nhóm). Các test dưới đây khóa lại những con số
đó để không ai làm trôi đáp án khi sửa mã.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import stats_classroom as sc
import stats_tools as stt


# ---------------------------------------------------------------------------
# Registry phòng: ba phòng riêng, mặc định theo lớp
# ---------------------------------------------------------------------------

def test_three_rooms_with_distinct_sgk_anchors():
    assert set(sc.ROOM_ORDER) == {sc.ROOM_10, sc.ROOM_11, sc.ROOM_12}
    assert sc.ROOM_LESSON_IDS == {
        sc.ROOM_10: "s2_so_dac_trung",
        sc.ROOM_11: "s3_mau_ghep_nhom",
        sc.ROOM_12: "s4_phan_tan_ghep_nhom",
    }


def test_default_room_follows_grade_level():
    assert sc.default_room_for_grade("lop_10") == sc.ROOM_10
    assert sc.default_room_for_grade("lop_11") == sc.ROOM_11
    assert sc.default_room_for_grade("lop_12") == sc.ROOM_12
    # Sinh viên và "Khác" không có phòng riêng: đưa về phòng Toán 10.
    assert sc.default_room_for_grade("sinh_vien") == sc.ROOM_10
    assert sc.default_room_for_grade("khac") == sc.ROOM_10


def test_every_step_and_exit_question_resolves_for_scenario():
    for room in sc.ROOM_ORDER:
        data = sc.scenario_data(room)
        sa, sb = sc.resolve_summaries(data)
        for step in sc.steps_for_room(room):
            assert step.fields, f"{room}/{step.step_id} thiếu ô dự đoán"
            for field in step.fields:
                value = sc.field_answer(field, sa, sb)
                assert math.isfinite(value), (room, step.step_id, field.answer_key)
            assert step.reveal(sa, sb)
        for question in sc.exit_questions(room):
            if question.answer_key:
                assert math.isfinite(question.answer(sa, sb))


# ---------------------------------------------------------------------------
# Số giáo án phòng Toán 10 (mẫu không ghép nhóm)
# ---------------------------------------------------------------------------

def test_scenario_room10_numbers_match_teaching_plan():
    data = sc.scenario_data(sc.ROOM_10)
    sa, sb = sc.resolve_summaries(data)
    # Cùng trung tâm: x̄ = Me = 0,2 cho cả A và B.
    for s in (sa, sb):
        assert s["mean"] == pytest.approx(0.2)
        assert s["median"] == pytest.approx(0.2)
    assert sa["mode"] == pytest.approx(0.2)
    assert sb["mode"] == pytest.approx(0.3)
    # Phân tán hoàn toàn khác nhau.
    assert sa["range"] == pytest.approx(0.9)
    assert sb["range"] == pytest.approx(4.1)
    assert sa["iqr"] == pytest.approx(0.1)
    assert sb["iqr"] == pytest.approx(1.6)
    assert sa["variance"] == pytest.approx(0.056)
    assert sb["variance"] == pytest.approx(1.328)
    assert sa["std"] == pytest.approx(0.236643, abs=1e-5)
    assert sb["std"] == pytest.approx(1.152388, abs=1e-5)
    # Quy tắc 1,5·IQR: A có outlier, B không.
    assert sa["outliers"] == (-0.2, 0.5, 0.7)
    assert sa["fence_low"] == pytest.approx(-0.05)
    assert sa["fence_high"] == pytest.approx(0.35)
    assert not sb["outliers"]
    assert sb["fence_low"] == pytest.approx(-3.0)
    assert sb["fence_high"] == pytest.approx(3.4)


# ---------------------------------------------------------------------------
# Số giáo án phòng Toán 11/12 (bảng tần số ghép nhóm)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("room", [sc.ROOM_11, sc.ROOM_12])
def test_scenario_grouped_numbers_match_teaching_plan(room):
    data = sc.scenario_data(room)
    sa, sb = sc.resolve_summaries(data)
    assert sa["mean"] == pytest.approx(0.2)
    assert sb["mean"] == pytest.approx(0.2)
    assert sa["median"] == pytest.approx(2.0 / 7.0)
    assert sb["median"] == pytest.approx(-0.125)
    assert sa["mode"] == pytest.approx(0.4)
    assert sb["mode"] == pytest.approx(-0.5)
    assert sa["q1"] == pytest.approx(-0.6)
    assert sa["q3"] == pytest.approx(1.0)
    assert sa["iqr"] == pytest.approx(1.6)
    assert sb["q1"] == pytest.approx(-0.75)
    assert sb["q3"] == pytest.approx(1.4)
    assert sb["iqr"] == pytest.approx(2.15)
    assert sa["variance"] == pytest.approx(1.41)
    assert sb["variance"] == pytest.approx(1.81)
    assert sa["std"] == pytest.approx(1.187434, abs=1e-5)
    assert sb["std"] == pytest.approx(1.345362, abs=1e-5)


# ---------------------------------------------------------------------------
# LaTeX bám SGK và hướng dẫn bấm máy Casio ở mọi bước
# ---------------------------------------------------------------------------

def test_every_step_has_sgk_latex_and_casio_guide():
    for room in sc.ROOM_ORDER:
        for step in sc.steps_for_room(room):
            assert step.latex, f"{room}/{step.step_id} thiếu công thức SGK"
            assert "\\" in step.latex
            assert not step.latex.lstrip().startswith("$"), (room, step.step_id)
            assert step.latex_note, f"{room}/{step.step_id} thiếu chú giải ký hiệu"
            assert step.casio, f"{room}/{step.step_id} thiếu hướng dẫn Casio"


def test_casio_guides_cover_both_models_and_machine_limits():
    # Bước 1 mỗi phòng: đủ cả hai dòng máy và bảng ký hiệu SGK ↔ máy.
    assert "fx-580VN X" in sc._CASIO_R10_STEP1 and "fx-880BTG" in sc._CASIO_R10_STEP1
    assert "fx-580VN X" in sc._CASIO_R11_STEP1 and "fx-880BTG" in sc._CASIO_R11_STEP1
    assert "σ²x" in sc._CASIO_R10_STEP1 and "Med" in sc._CASIO_R10_STEP1
    # Dữ liệu ghép nhóm: phải cảnh báo máy không nội suy được Me/Mo/Q.
    assert "không" in sc._CASIO_R11_STEP1 and "nội suy" in sc._CASIO_R11_STEP1
    # Phòng 10 bước 4: cảnh báo đừng nhầm σ²x (chia n) với s²x (chia n − 1).
    r10_std = next(s for s in sc.room10_steps() if s.step_id == "std")
    assert "n − 1" in r10_std.casio


def test_summarize_grouped_from_freq_validation():
    mids = [-2.5, -1.5, -0.5, 0.5, 1.5, 2.5]
    with pytest.raises(ValueError):
        stt.summarize_grouped_from_freq(mids, [1, 2])            # lệch độ dài
    with pytest.raises(ValueError):
        stt.summarize_grouped_from_freq([-2.5, -1.5, 0.5], [1, 1, 1])  # không đều
    with pytest.raises(ValueError):
        stt.summarize_grouped_from_freq([-2.5, -1.5], [0, 0])    # tổng tần số 0
    with pytest.raises(ValueError):
        stt.summarize_grouped_from_freq([-1.5, -2.5], [1, 1])    # trung điểm giảm dần
    with pytest.raises(ValueError):
        stt.summarize_grouped_from_freq([-1.5], [1])             # một nhóm


def test_summarize_grouped_from_freq_derives_boundaries_and_labels():
    result = stt.summarize_grouped_from_freq([-2.5, -1.5, -0.5], [2, 3, 5])
    assert result["boundaries"] == pytest.approx([-3.0, -2.0, -1.0, 0.0])
    assert result["n_total"] == 10
    assert result["labels"][0].startswith("[-3")
    assert result["labels"][-1].endswith("]")  # nhóm cuối đóng hai đầu


# ---------------------------------------------------------------------------
# Nguồn dữ liệu nhập tay và từ dữ liệu đã nạp
# ---------------------------------------------------------------------------

def test_room10_manual_parses_two_series():
    data = sc.room10_manual("-0.2, 0.1, 0.2, 0.5", "0, 1, -1, 2")
    sa, sb = sc.resolve_summaries(data)
    assert sa["mean"] == pytest.approx(0.15)
    assert sb["mean"] == pytest.approx(0.5)


def test_room11_manual_and_real_share_uniform_grid():
    # Tần số đối xứng quanh 0 (mids cách đều): 1·(−2,5)+2·(−1,5)+2·(−0,5)+1·0,5.
    data = sc.room11_manual("-2.5, -1.5, -0.5, 0.5", "1, 2, 2, 1", "1, 2, 2, 1")
    assert data.is_grouped
    sa, _ = sc.resolve_summaries(data)
    assert sa["mean"] == pytest.approx(-1.0)


def test_room11_from_prices_uses_common_grid_for_both_halves():
    # 40 phiên tăng dần nhẹ: hai nửa rơi vào các nhóm khác nhau nhưng chung lưới.
    prices = pd.DataFrame({
        "AAA": [100.0 + i * 0.1 for i in range(41)],
        "VNINDEX": [100.0] * 41,
    })
    data = sc.room11_from_prices(prices, "VNINDEX", "AAA", 20)
    assert data.is_grouped
    assert sum(data.freqs_a) == 20
    assert sum(data.freqs_b) == 20
    assert data.freqs_a != data.freqs_b


def test_room10_from_prices_returns_pct_returns():
    prices = pd.DataFrame({
        "AAA": [100.0, 101.0, 102.0, 101.0, 100.0, 101.0],
        "BBB": [200.0, 202.0, 201.0, 203.0, 202.0, 204.0],
        "VNINDEX": [1000.0] * 6,
    })
    data = sc.room10_from_prices(prices, "VNINDEX", "AAA", "BBB", 5)
    sa, sb = sc.resolve_summaries(data)
    assert data.names == ("AAA", "BBB")
    assert sa["n"] == 5 and sb["n"] == 5
    assert sa["mean"] == pytest.approx(sum(
        [(101 / 100 - 1), (102 / 101 - 1), (101 / 102 - 1), (100 / 101 - 1), (101 / 100 - 1)]
    ) / 5 * 100)


# ---------------------------------------------------------------------------
# Exit ticket: chấm điểm và ghi hồ sơ
# ---------------------------------------------------------------------------

def test_grade_exit_full_and_empty():
    for room in sc.ROOM_ORDER:
        sa, sb = sc.resolve_summaries(sc.scenario_data(room))
        questions = sc.exit_questions(room)
        full = {}
        empty = {}
        for q in questions:
            if q.kind == sc.KIND_SINGLE:
                full[q.qid] = q.correct_index
            else:
                full[q.qid] = q.answer(sa, sb) + q.tolerance(sa, sb) * 0.5
            empty[q.qid] = None
        score, correct = sc.grade_exit(questions, full, sa, sb)
        assert score == 100 and all(correct.values())
        score, correct = sc.grade_exit(questions, empty, sa, sb)
        assert score == 0 and not any(correct.values())


def test_grade_exit_partial_scores_two_thirds():
    sa, sb = sc.resolve_summaries(sc.scenario_data(sc.ROOM_10))
    questions = sc.exit_questions(sc.ROOM_10)
    responses = {}
    for q in questions:
        if q.kind == sc.KIND_SINGLE:
            responses[q.qid] = None  # bỏ trống câu khái niệm
        else:
            responses[q.qid] = q.answer(sa, sb)
    score, correct = sc.grade_exit(questions, responses, sa, sb)
    assert score == 67
    assert correct["q2"] and correct["q3"] and not correct["q1"]


def test_exit_ticket_number_tolerance_rejects_wrong_answer():
    sa, sb = sc.resolve_summaries(sc.scenario_data(sc.ROOM_11))
    questions = sc.exit_questions(sc.ROOM_11)
    q2 = next(q for q in questions if q.qid == "q2")
    score, correct = sc.grade_exit(questions, {"q2": q2.answer(sa, sb) + 1.0}, sa, sb)
    assert not correct["q2"] and score == 0


# ---------------------------------------------------------------------------
# Biểu đồ và bảng tổng kết dựng được không cần trình duyệt
# ---------------------------------------------------------------------------

def test_charts_and_summary_build_for_both_data_shapes():
    raw = sc.scenario_data(sc.ROOM_10)
    dots, box = sc.room10_charts(raw)
    assert dots is not None and box is not None
    grouped = sc.scenario_data(sc.ROOM_11)
    bars, ogive = sc.grouped_charts(grouped)
    assert bars is not None and ogive is not None
    for room in sc.ROOM_ORDER:
        data = sc.scenario_data(room)
        sa, sb = sc.resolve_summaries(data)
        table = sc.summary_table(data, sa, sb)
        assert list(table.columns) == ["Số đặc trưng", data.names[0], data.names[1]]
        assert len(table) >= 10


# ---------------------------------------------------------------------------
# Smoke: dựng nổi cả ba phòng qua AppTest (nguồn kịch bản mặc định)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("room_index", [0, 1, 2])
def test_render_room_smoke(room_index):
    at = AppTest.from_string(
        "import streamlit as st\n"
        "import stats_classroom as sc\n"
        "st.session_state['qa_class_room'] = "
        f"({sc.ROOM_10!r}, {sc.ROOM_11!r}, {sc.ROOM_12!r})[{room_index}]\n"
        "import pandas as pd\n"
        "sc.render_stats_classroom(pd.DataFrame(), 'VNINDEX')",
        default_timeout=60,
    ).run()
    assert not at.exception
    # Nguồn mặc định là bộ kịch bản: caption nguồn phải xuất hiện.
    assert any("Nguồn đang dùng" in c.value for c in at.caption)
