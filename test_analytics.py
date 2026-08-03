import sys
import types
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import analytics


def _sample_returns(rows=120):
    rng = np.random.default_rng(20260803)
    common = rng.normal(0.0004, 0.008, rows)
    return pd.DataFrame(
        {
            "AAA": 0.0005 + 0.8 * common + rng.normal(0, 0.004, rows),
            "BBB": 0.0003 + 0.4 * common + rng.normal(0, 0.006, rows),
            "CCC": 0.0007 + 1.2 * common + rng.normal(0, 0.005, rows),
        }
    )


def _sim_rows():
    return [
        {
            "Mã CP": "AAA",
            "Beta (Độ nhạy)": 1.2,
            "Alpha": 0.0002,
            "R^2": 0.42,
            "Rủi ro Hệ thống": 0.0001,
            "Rủi ro Phi hệ thống": 0.0002,
            "Tổng Rủi ro": 0.0003,
        }
    ]


def _opt_result():
    return {
        "assets": ["AAA", "BBB"],
        "max_sharpe_weights": np.array([0.6, 0.4]),
        "max_sharpe_cash_weight": 0.0,
        "risk_free_rate": 0.04,
        "warning": None,
        "optimizer_status": {
            "max_sharpe": {"success": True, "mode": "risky_portfolio"}
        },
    }


def test_run_sim_and_diagnostics_validate_contract():
    rng = np.random.default_rng(7)
    market = pd.Series(rng.normal(0.0004, 0.01, 100), name="market")
    asset = 0.0002 + 1.4 * market + pd.Series(rng.normal(0, 0.002, 100))

    result = analytics.run_sim(asset, market)
    assert result["n_observations"] == 100
    assert result["beta"] == pytest.approx(1.4, abs=0.06)
    assert np.isfinite(
        [
            result["alpha"],
            result["beta"],
            result["systematic_risk"],
            result["unsystematic_risk"],
        ]
    ).all()

    diagnostics = analytics.run_diagnostics(result)
    assert diagnostics["status"] in {"ok", "partial"}
    assert diagnostics["n_observations"] == 100
    assert set(diagnostics) >= {
        "White_pvalue",
        "BG_pvalue",
        "RESET_pvalue",
        "JB_pvalue",
        "errors",
    }


def test_sim_and_diagnostics_reject_too_few_observations():
    short = pd.Series([0.01, 0.02, 0.03])
    with pytest.raises(analytics.AnalyticsValidationError, match="ít nhất"):
        analytics.run_sim(short, short * 0.5)

    rng = np.random.default_rng(9)
    market = pd.Series(rng.normal(0, 0.01, 12))
    result = analytics.run_sim(market * 1.1, market)
    with pytest.raises(analytics.AnalyticsValidationError, match="ít nhất"):
        analytics.run_diagnostics(result, min_observations=20)


def test_markowitz_nominal_is_finite_bounded_and_deterministic():
    returns = _sample_returns()
    first = analytics.markowitz_optimization(returns, random_seed=123)
    second = analytics.markowitz_optimization(returns, random_seed=123)

    legacy_keys = {
        "min_vol_weights",
        "max_sharpe_weights",
        "assets",
        "warning",
        "ef_vols",
        "ef_rets",
        "ef_sharpes",
    }
    assert legacy_keys <= set(first)
    for key in ("min_vol_weights", "max_sharpe_weights"):
        weights = np.asarray(first[key])
        assert np.isfinite(weights).all()
        assert (weights >= -1e-12).all()
        assert (weights <= 1 + 1e-12).all()
        assert weights.sum() == pytest.approx(1.0, abs=1e-8)
    assert first["cash_weight"] == 0.0
    assert first["optimizer_status"]["min_vol"]["success"] is True
    np.testing.assert_allclose(first["ef_vols"], second["ef_vols"])
    np.testing.assert_allclose(first["ef_rets"], second["ef_rets"])
    np.testing.assert_allclose(first["ef_sharpes"], second["ef_sharpes"])


def test_markowitz_regularizes_collinear_covariance():
    x = np.linspace(-0.01, 0.02, 80)
    returns = pd.DataFrame({"AAA": x, "BBB": 2.0 * x + 0.0001})
    result = analytics.markowitz_optimization(returns, min_observations=20)
    eigenvalues = np.linalg.eigvalsh(result["regularized_covariance"].to_numpy())
    assert result["covariance_regularization"] > 0
    assert (eigenvalues > 0).all()
    assert np.isfinite(result["ef_vols"]).all()


def test_markowitz_uses_cash_when_no_risky_asset_beats_risk_free_rate():
    x = np.linspace(-0.01, 0.01, 80)
    returns = pd.DataFrame(
        {
            "AAA": -0.0005 + x,
            "BBB": -0.0003 + np.sin(np.arange(80)) * 0.002,
        }
    )
    result = analytics.markowitz_optimization(returns, risk_free_rate=0.04)
    np.testing.assert_allclose(result["max_sharpe_weights"], np.zeros(2))
    assert result["max_sharpe_cash_weight"] == pytest.approx(1.0)
    assert result["optimizer_status"]["max_sharpe"]["mode"] == "cash"
    assert "tiền mặt" in result["warning"].lower()


def test_markowitz_rejects_short_or_degenerate_samples():
    with pytest.raises(analytics.AnalyticsValidationError, match="ít nhất"):
        analytics.markowitz_optimization(_sample_returns(rows=10))
    constant = pd.DataFrame({"AAA": np.ones(30) * 0.001})
    with pytest.raises(analytics.AnalyticsValidationError, match="không có đủ biến động"):
        analytics.markowitz_optimization(constant)


def test_markowitz_rejects_solver_failure_and_invalid_weights(monkeypatch):
    failed = SimpleNamespace(success=False, message="forced failure", x=np.array([0.5] * 3))
    monkeypatch.setattr(analytics, "minimize", lambda *args, **kwargs: failed)
    with pytest.raises(analytics.AnalyticsValidationError, match="forced failure"):
        analytics.markowitz_optimization(_sample_returns())

    invalid = SimpleNamespace(success=True, message="fake success", x=np.array([2.0, -1.0, 0.0]))
    monkeypatch.setattr(analytics, "minimize", lambda *args, **kwargs: invalid)
    with pytest.raises(analytics.AnalyticsValidationError, match="ngoài miền"):
        analytics.markowitz_optimization(_sample_returns())


def test_call_llm_extracts_all_anthropic_text_blocks(monkeypatch):
    captured = {}

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                content=[
                    SimpleNamespace(type="thinking", text="hidden"),
                    {"type": "text", "text": "Phần một"},
                    SimpleNamespace(type="text", text="Phần hai"),
                ]
            )

    class FakeAnthropic:
        def __init__(self, api_key):
            captured["api_key"] = api_key
            self.messages = FakeMessages()

        def close(self):
            captured["closed"] = True

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=FakeAnthropic))
    output = analytics.call_llm(
        "prompt",
        {
            "provider": "Anthropic (Claude)",
            "model": "claude-test",
            "api_key": "secret",
        },
    )
    assert output == "Phần một\nPhần hai"
    assert captured["model"] == "claude-test"
    assert captured["closed"] is True


def test_call_llm_uses_per_call_google_genai_client_and_default_model(monkeypatch):
    captured = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(text="Diễn giải an toàn")

    class FakeClient:
        def __init__(self, api_key):
            captured["api_key"] = api_key
            self.models = FakeModels()

        def close(self):
            captured["closed"] = True

    fake_genai = SimpleNamespace(Client=FakeClient)
    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    output = analytics.call_llm(
        "prompt",
        {"provider": "Google (Gemini)", "model": "", "api_key": "secret"},
    )
    assert output == "Diễn giải an toàn"
    assert captured["model"] == "gemini-3.1-pro-preview"
    assert captured["contents"] == "prompt"
    assert captured["closed"] is True


def test_expert_advice_sends_structured_metrics_only(monkeypatch):
    captured = {}

    def fake_llm(prompt, config):
        captured["prompt"] = prompt
        return "Beta mô tả độ nhạy lịch sử; kết quả còn phụ thuộc sai số ước lượng."

    monkeypatch.setattr(analytics, "call_llm", fake_llm)
    output = analytics.generate_expert_advice(
        _sim_rows(),
        _opt_result(),
        pd.Series(np.linspace(100, 110, 40)),
        {"provider": "Google (Gemini)", "api_key": "secret"},
    )
    assert "METRICS_JSON" in captured["prompt"]
    assert '"scope": "historical_sample_only"' in captured["prompt"]
    assert "không phải khuyến nghị" in output.lower()
    assert "giải ngân phần lớn" not in output.lower()


def test_expert_advice_rejects_actionable_llm_language(monkeypatch):
    monkeypatch.setattr(
        analytics,
        "call_llm",
        lambda prompt, config: "Nên mua AAA và giải ngân phần lớn ngay.",
    )
    output = analytics.generate_expert_advice(
        _sim_rows(),
        _opt_result(),
        pd.Series(np.linspace(100, 110, 40)),
        {"provider": "Google (Gemini)", "api_key": "secret"},
    )
    assert "đã bị loại" in output
    assert "giải ngân phần lớn ngay" not in output
    assert "không phải khuyến nghị mua/bán" in output.lower()
