from pathlib import Path
import json

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import learning_modes as lm
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
