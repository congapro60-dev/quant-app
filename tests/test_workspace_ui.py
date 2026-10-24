from pathlib import Path
import json

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import curriculum as cur
import learning_modes as lm
import progress_profile as pp
import workspace_ui as wu
from workspace_ui import HISTORY_LABEL, MUSE_LABEL, NAV_KEY, history_view

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_history_comparison_does_not_mix_index_points_with_price_units():
    prices = pd.DataFrame({"CTG": [30.0, 33.0], "VNINDEX": [1200.0, 1260.0]})
    pd.testing.assert_frame_equal(history_view(prices, ["CTG", "VNINDEX"], rebase=True),
                                  pd.DataFrame({"CTG": [100.0, 110.0], "VNINDEX": [100.0, 105.0]}))
    assert prices.iloc[0].tolist() == [30.0, 1200.0]
    pd.testing.assert_frame_equal(history_view(prices, ["CTG"], rebase=False), prices[["CTG"]])


@pytest.mark.parametrize("bad", [0, -1, np.nan, np.inf])
def test_history_rejects_invalid_prices(bad):
    with pytest.raises(ValueError):
        history_view(pd.DataFrame({"CTG": [bad, 31.0]}), ["CTG"], rebase=True)


def test_home_actions_reach_requested_tabs_and_return_from_muse():
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    assert at.session_state[NAV_KEY] == "Tổng quan"
    at.button(key=f"start_{lm.AREA_DATA}").click().run()
    assert at.session_state[NAV_KEY] == lm.AREA_LABELS[lm.AREA_DATA]
    assert at.session_state[f"tools_{lm.AREA_DATA}"] == HISTORY_LABEL
    at.button(key=f"start_{lm.AREA_INVEST}").click().run()
    assert at.session_state[f"tools_{lm.AREA_INVEST}"] == lm.FEATURES[lm.FEATURE_PAPER]["label"]
    at.button(key="overview_muse").click().run()
    assert at.session_state[f"tools_{lm.AREA_LEARNING}"] == MUSE_LABEL
    at.button(key=f"start_{lm.AREA_LEARNING}").click().run()
    assert at.session_state[f"tools_{lm.AREA_LEARNING}"] == "Bài học và thực hành"
    assert not at.exception


def test_hidden_lab_selection_resets_without_losing_ledger():
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state[NAV_KEY] = lm.AREA_LABELS[lm.AREA_MODEL_LAB]
    at.session_state["trade_plans"] = {"kept": "plan"}
    at.run()
    assert not at.exception
    assert at.session_state[NAV_KEY] == "Tổng quan"
    assert at.session_state["trade_plans"] == {"kept": "plan"}


def test_overview_counts_ledger_fills_not_obsolete_paper_trades():
    at = AppTest.from_string("from workspace_ui import render_overview\nrender_overview()", default_timeout=30)
    at.session_state["paper_ledger"] = {"fills": [{"symbol": "CTG"}, {"symbol": "FPT"}]}
    at.session_state["paper_trades"] = []
    at.run()
    assert not at.exception
    assert next(m.value for m in at.metric if m.label == "Giao dịch mô phỏng") == "2"


def test_history_error_never_displays_old_prices():
    at = AppTest.from_string("from workspace_ui import render_history\nrender_history()", default_timeout=30)
    at.session_state["prices_df"] = pd.DataFrame({"CTG": [30, 31]}, index=pd.date_range("2026-01-01", periods=2))
    at.session_state["data_status"] = "error"
    at.run()
    assert not at.exception
    assert not at.get("plotly_chart") and not at.dataframe


def test_history_raw_prices_separate_market_index():
    at = AppTest.from_string("from workspace_ui import render_history\nrender_history()", default_timeout=30)
    at.session_state["prices_df"] = pd.DataFrame({"CTG": [30, 31], "VNINDEX": [1200, 1230]}, index=pd.date_range("2026-01-01", periods=2))
    at.session_state["prices_df"].index.name = "time"
    at.session_state["market_ticker"] = "VNINDEX"
    at.session_state["data_status"] = "ok"
    at.session_state["history_symbols"] = ["CTG", "VNINDEX"]
    at.session_state["history_rebase"] = False
    at.run()
    assert not at.exception
    assert len(at.get("plotly_chart")) == 2
    for chart in at.get("plotly_chart"):
        assert json.loads(chart.proto.spec)["layout"]["xaxis"]["title"]["text"] == "Phiên"
    assert at.dataframe[0].value["Đơn vị"].tolist() == ["Nghìn VND/cổ phiếu", "Điểm"]


# ---------------------------------------------------------------------------
# Onboarding C2: Hành trình lần đầu 5 bước trên Trang tổng quan
# ---------------------------------------------------------------------------

def _journey_buttons(at):
    return sorted(b.key for b in at.button if b.key and b.key.startswith("journey_"))


def test_first_journey_visible_and_navigates_for_newcomer():
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception

    # Người mới: 5 bước chưa làm gì, mỗi bước một nút nhảy sang khu của nó.
    assert _journey_buttons(at) == [f"journey_{i}" for i in range(5)] + ["journey_hide"]

    at.button(key="journey_0").click().run()
    assert at.session_state[NAV_KEY] == lm.AREA_LABELS[lm.AREA_JOURNAL]

    at.button(key="journey_2").click().run()
    assert at.session_state[f"tools_{lm.AREA_INVEST}"] == lm.FEATURES[lm.FEATURE_PAPER]["label"]


def _fully_done_profile(at):
    profile = pp.empty_profile()
    first = cur.all_lessons()[0].lesson_id
    profile["pre_test"] = {"score": 40.0, "taken_at": "2026-10-24 20:12"}
    profile["lesson_scores"] = {first: 85.0}
    pp.add_journal_entry(profile, title="Thử", decision="Mua 1 mã.")
    at.session_state["progress_profile"] = profile
    at.session_state["paper_ledger"] = {"fills": [{"qty": 100}]}
    at.session_state[wu.BACKUP_FLAG_KEY] = True


def test_first_journey_hides_when_all_five_steps_done():
    at = AppTest.from_file(APP, default_timeout=120).run()
    _fully_done_profile(at)
    at.run()

    assert not at.exception
    assert _journey_buttons(at) == []


def test_first_journey_dismiss_button_hides_until_next_session():
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.button(key="journey_hide").click().run()
    assert _journey_buttons(at) == []
    assert at.session_state[wu.JOURNEY_HIDE_KEY] is True


# ---------------------------------------------------------------------------
# Onboarding C3: Tour chào mừng 4 bước, tự mở một lần với hồ sơ mới
# ---------------------------------------------------------------------------

def test_first_tour_opens_then_defer_marks_seen_for_good():
    """Lần đầu: tour mở; bấm 'Để sau' là không bao giờ mở lại."""

    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    assert [b.key for b in at.button if b.key in ("tour_defer", "tour_next")]
    # Bước 1/4: chưa có nút lùi.
    assert [b for b in at.button if b.key == "tour_back"] == []

    at.button(key="tour_defer").click().run()
    assert at.session_state["progress_profile"]["seen_tour"] is True
    assert not [b for b in at.button if b.key and b.key.startswith("tour_")]


def test_first_tour_finish_marks_seen_and_navigates(monkeypatch):
    """Xong tour: cờ seen được ghi, đổi khu, VÀ buộc rerun cả app.

    Bài học từ lỗi thật trên production: st.dialog chạy như fragment, nên
    bấm nút cuối chỉ rerun riêng dialog; thiếu st.rerun() thì NAV_KEY đổi
    mà thanh tab không dựng lại, màn hình vẫn đứng ở Tổng quan. AppTest
    rerun cả app nên không tự bắt được — phải khoá hợp đồng này lại.
    """

    import workspace_ui as wu

    reruns: list[int] = []
    monkeypatch.setattr(wu.st, "rerun", lambda *a, **k: reruns.append(1))

    at = AppTest.from_file(APP, default_timeout=120).run()
    at.button(key="tour_next").click().run()
    at.button(key="tour_next").click().run()
    at.button(key="tour_next").click().run()
    at.button(key="tour_finish").click().run()

    assert reruns == [1], "Nút cuối tour phải gọi st.rerun để dựng lại thanh tab."
    assert at.session_state["progress_profile"]["seen_tour"] is True
    assert at.session_state[NAV_KEY] == lm.AREA_LABELS[lm.AREA_JOURNAL]
    assert not [b for b in at.button if b.key and b.key.startswith("tour_")]


def test_mark_tour_seen_is_pure_and_does_not_rerun(monkeypatch):
    """Cờ seen chỉ ghi state; không rerun để tránh vòng lặp khi mở tour."""

    import workspace_ui as wu

    reruns: list[int] = []
    monkeypatch.setattr(wu.st, "rerun", lambda *a, **k: reruns.append(1))
    monkeypatch.setitem(wu.st.session_state, "progress_profile", {"seen_tour": False})

    wu._mark_tour_seen()

    assert wu.st.session_state["progress_profile"]["seen_tour"] is True
    assert reruns == []


def test_first_tour_never_opens_when_profile_has_progress():
    """Hồ sơ đã có hoạt động thì tour không mở, kể cả chưa từng thấy cờ."""

    at = AppTest.from_file(APP, default_timeout=120).run()
    _fully_done_profile(at)
    at.run()
    assert not at.exception
    assert not [b for b in at.button if b.key and b.key.startswith("tour_")]
    assert at.session_state["progress_profile"]["seen_tour"] is False


# ---------------------------------------------------------------------------
# Onboarding C4: bảng "Tab nào — khi nào" cuối Trang tổng quan
# ---------------------------------------------------------------------------

def test_tab_map_lists_all_five_areas_with_timing():
    """Bảng chỉ đường phải đủ 5 khu vực, đúng nhãn thật của thanh tab."""

    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception

    tables = [t.value for t in at.dataframe if "Khu vực" in list(t.value.columns)]
    assert len(tables) == 1
    table = tables[0]
    assert list(table.columns) == ["Khu vực", "Dùng để", "Khi nào"]
    assert table["Khu vực"].tolist() == [lm.AREA_LABELS[a] for a in lm.AREA_ORDER]
    assert table["Khi nào"].str.len().min() > 0
    assert table["Dùng để"].str.len().min() > 0
