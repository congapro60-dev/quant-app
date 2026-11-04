"""Web phải ra đúng số của EViews 4 thật.

Số vàng dưới đây đọc từ bảng kết quả EViews 4 chạy ngày 02/11/2026 trên 150 quan
sát trong ``fixtures/eviews_parity_150.csv``. Lệch một chữ số là test đỏ.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

import eviews_emulator as ev

GOLD = {
    "VIC": dict(adf=-6.693509, gamma=0.052894, beta=0.959152, se=0.143669, t=6.676134, r2=0.232660,
                sereg=0.017197, ssr=0.043471, llf=394.9783, aic=-5.274876, sc=-5.234555, f=44.57076,
                dw=1.995984, white_f=6.717739, white_p=0.001618, white_lm=12.55609, white_lmp=0.001877,
                bg_f=0.111482, bg_p=0.738942, bg_lm=0.113686, bg_lmp=0.735986, reset_f=0.664432, reset_p=0.416327),
    "REE": dict(adf=-6.633421, gamma=-0.930927, beta=0.727000, se=0.090340, t=8.047377, r2=0.305819,
                sereg=0.010813, ssr=0.017189, llf=464.1040, aic=-6.202738, sc=-6.162417, f=64.76028,
                dw=2.195401, white_f=0.031641, white_p=0.968861, white_lm=0.064554, white_lmp=0.968238,
                bg_f=1.528475, bg_p=0.218327, bg_lm=1.543721, bg_lmp=0.214065, reset_f=0.642350, reset_p=0.424164),
    "STB": dict(adf=-5.681675, gamma=-1.128800, beta=0.958097, se=0.163231, t=5.869561, r2=0.189867,
                sereg=0.019538, ssr=0.056116, llf=375.9572, aic=-5.019559, sc=-4.979238, f=34.45175,
                dw=1.976979, white_f=0.312342, white_p=0.732219, white_lm=0.634804, white_lmp=0.728038,
                bg_f=0.012962, bg_p=0.909511, reset_f=0.038580, reset_p=0.844556),
}


@pytest.fixture(scope="module")
def data():
    df = pd.read_csv(Path(__file__).parent / "fixtures" / "eviews_parity_150.csv")
    for name in ("VIC", "REE", "STB", "VNINDEX"):
        df = ev.parse_and_execute_command(f"GENR R_{name} = LOG({name})-LOG({name}(-1))", df)["data"]
    return df


def _text(result):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", ev.format_eviews_output(result)))


@pytest.mark.parametrize("name", list(GOLD))
def test_adf_matches_eviews(data, name):
    a = ev.parse_and_execute_command(f"ADF R_{name}", data)["adf"]
    assert a["stat"] == pytest.approx(GOLD[name]["adf"], abs=1e-6)
    assert a["nobs"] == 144 and a["lags"] == 4
    assert round(a["crit"]["1%"], 4) == -3.4767
    assert round(a["crit"]["5%"], 4) == -2.8815
    assert round(a["crit"]["10%"], 4) == -2.5773


def test_critical_values_match_the_lecture_table_too():
    crit = ev.mackinnon_critical_values(394)
    assert (round(crit["1%"], 4), round(crit["5%"], 4), round(crit["10%"], 4)) == (-3.4490, -2.8691, -2.5708)


@pytest.mark.parametrize("name", list(GOLD))
def test_regression_matches_eviews(data, name):
    g, r = GOLD[name], ev.parse_and_execute_command(f"LS R_{name} C R_VNINDEX", data)["results"]
    assert r.params["R_VNINDEX"] == pytest.approx(g["beta"], abs=1e-6)
    assert r.bse["R_VNINDEX"] == pytest.approx(g["se"], abs=1e-6)
    assert r.tvalues["R_VNINDEX"] == pytest.approx(g["t"], abs=1e-6)
    assert r.rsquared == pytest.approx(g["r2"], abs=1e-6)
    assert r.llf == pytest.approx(g["llf"], abs=1e-4)
    assert r.fvalue == pytest.approx(g["f"], abs=1e-4)
    assert r.tvalues["const"] == pytest.approx(g["gamma"], abs=1e-6)


@pytest.mark.parametrize("name", list(GOLD))
def test_displayed_table_matches_eviews(data, name):
    g, text = GOLD[name], _text(ev.parse_and_execute_command(f"LS R_{name} C R_VNINDEX", data))
    for key in ("sereg", "ssr", "aic", "sc", "dw", "white_f", "white_p", "white_lm", "white_lmp"):
        assert f"{g[key]:.6f}" in text, key
    if g.get("bg_f") is not None:
        assert f"{g['bg_f']:.6f}" in text and f"{g['bg_p']:.6f}" in text
    if g.get("reset_f") is not None:
        assert f"{g['reset_f']:.6f}" in text and f"{g['reset_p']:.6f}" in text


def test_covariance_matches_eviews_table(data):
    cov = ev.parse_and_execute_command("COV R_VIC R_REE R_STB", data)["cov"]
    assert round(cov.loc["R_VIC", "R_VIC"], 6) == 0.000380
    assert round(cov.loc["R_REE", "R_REE"], 6) == 0.000166
    assert round(cov.loc["R_STB", "R_STB"], 6) == 0.000465
    assert round(cov.loc["R_VIC", "R_REE"] * 1e5, 2) == 5.39


def test_portfolio_regression_matches_eviews(data):
    df = ev.parse_and_execute_command("GENR R_P = 0.5*R_VIC-0.2*R_REE+0.7*R_STB", data)["data"]
    r = ev.parse_and_execute_command("LS R_P C R_VNINDEX", df)["results"]
    assert r.params["R_VNINDEX"] == pytest.approx(1.004844, abs=1e-6)
    assert r.rsquared == pytest.approx(0.270391, abs=1e-6)


def test_smpl_keeps_the_first_observations(data):
    res = ev.parse_and_execute_command("SMPL 1 150", data)
    assert len(res["data"]) == 150
    assert "error" in ev.parse_and_execute_command("SMPL 0 10", data)
    assert "error" in ev.parse_and_execute_command("SMPL 1 9999", data)


def test_adf_lag_can_be_chosen_and_is_validated(data):
    assert ev.parse_and_execute_command("ADF R_VIC 2", data)["adf"]["lags"] == 2
    assert "error" in ev.parse_and_execute_command("ADF R_VIC abc", data)


# Số đọc từ bảng EViews 4 chạy LS(H) R_VIC C R_VNINDEX (149 quan sát, sai số chuẩn White HC1).
WHITE_VIC = dict(c_se=0.001399, b_se=0.191825, c_t=0.053435, b_t=5.000138, c_p=0.9575, b_p=0.0)


def test_ls_h_white_standard_errors_match_eviews(data):
    robust = ev.parse_and_execute_command("LS(H) R_VIC C R_VNINDEX", data)["coef_results"]
    assert robust.bse["const"] == pytest.approx(WHITE_VIC["c_se"], abs=5e-7)
    assert robust.bse["R_VNINDEX"] == pytest.approx(WHITE_VIC["b_se"], abs=5e-7)
    assert robust.tvalues["const"] == pytest.approx(WHITE_VIC["c_t"], abs=5e-7)
    assert robust.tvalues["R_VNINDEX"] == pytest.approx(WHITE_VIC["b_t"], abs=5e-7)
    assert round(robust.pvalues["const"], 4) == WHITE_VIC["c_p"]
    assert round(robust.pvalues["R_VNINDEX"], 4) == WHITE_VIC["b_p"]


def test_ls_h_keeps_ols_coefficients_and_f_statistic(data):
    plain = ev.parse_and_execute_command("LS R_VIC C R_VNINDEX", data)
    white = ev.parse_and_execute_command("LS(H) R_VIC C R_VNINDEX", data)
    assert "coef_results" not in plain
    assert list(white["results"].params) == pytest.approx(list(plain["results"].params))
    assert white["results"].fvalue == pytest.approx(GOLD["VIC"]["f"], abs=1e-5)


def test_ls_h_output_names_the_white_covariance(data):
    text = _text(ev.parse_and_execute_command("LS(H) R_VIC C R_VNINDEX", data))
    assert "White Heteroskedasticity-Consistent Standard Errors &amp; Covariance" in text
    assert "0.191825" in text


def test_ls_option_accepts_space_and_rejects_unknown_letters(data):
    spaced = ev.parse_and_execute_command("LS (H) R_VIC C R_VNINDEX", data)
    attached = ev.parse_and_execute_command("LS(H) R_VIC C R_VNINDEX", data)
    assert spaced["coef_results"].bse["R_VNINDEX"] == pytest.approx(attached["coef_results"].bse["R_VNINDEX"])
    assert "error" in ev.parse_and_execute_command("LS(X) R_VIC C R_VNINDEX", data)
