
import pytest

from pipelines.model.selector import LiveModelSelector, SelectionResult


def test_empty_results_returns_empty_selection():
    selector = LiveModelSelector(config={})

    result = selector.select([])

    assert isinstance(result, SelectionResult)
    assert result.best is None
    assert result.candidates == []
    assert result.rejected == []
    assert result.config["constraints"]["min_oos_ic"] == 0.0
    assert result.config["weights"]["oos_icir"] == pytest.approx(0.30)
