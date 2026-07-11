import pandas as pd

from app.engine.stats_engine import (
    classify_terms,
    factor_degree,
    fit_regression_model,
    fix_component,
    term_params,
    transform_term,
    update_factor_names,
    validate_num_runs,
)


def test_classify_terms() -> None:
    assert classify_terms("A") == 1
    assert classify_terms("A:B") == 2
    assert classify_terms("I(A**2)") == 1
    assert classify_terms("I(A**2):B") == 2


def test_factor_degree() -> None:
    components = ["x1", "x2", "x1:x1", "x1:x2"]
    assert factor_degree("x1", components) == 2
    assert factor_degree("x2", components) == 1
    assert factor_degree("x3", components) == 1


def test_fix_component() -> None:
    assert fix_component("x1") == "x1"
    assert fix_component("x1:x1") == "I(x1**2)"
    assert fix_component("x1:x1:x1") == "I(x1**3)"
    assert fix_component("x1:x2") == "x1:x2"


def test_term_params() -> None:
    factor_info = {
        "x1": {"name": "x1", "type": "Continuous", "levels": ["-1", "1"]},
        "x2": {"name": "x2", "type": "Categorical", "levels": ["A", "B", "C"]},
        "x3": {"name": "x3", "type": "Discrete", "levels": ["1", "2", "3"]},
    }
    assert term_params("x1", factor_info) == 1
    assert term_params("x2", factor_info) == 2
    assert term_params("x3", factor_info) == 2
    assert term_params("x1:x2", factor_info) == 2


def test_validate_num_runs() -> None:
    res = validate_num_runs(10, 5, 15)
    assert res["valid"] is True
    assert res["message"] is None

    res = validate_num_runs("10", 5, 15)
    assert res["valid"] is True

    res = validate_num_runs(4, 5, 15)
    assert res["valid"] is False
    assert "must be within the minumum and maximum" in res["message"]

    res = validate_num_runs(10.5, 5, 15)
    assert res["valid"] is False
    assert "must be an integer" in res["message"]

    res = validate_num_runs(0, 0, 15)
    assert res["valid"] is False
    assert "must be greater than zero" in res["message"]

    res = validate_num_runs("invalid", 5, 15)
    assert res["valid"] is False
    assert "must be a single numeric integer" in res["message"]


def test_transform_term() -> None:
    assert transform_term("A * A") == "I(A**2)"
    assert transform_term("A * B") == "A:B"
    assert transform_term("A") == "A"


def test_update_factor_names() -> None:
    design_matrix = pd.DataFrame(
        {
            "A": [-1, 1, -1, 1],
            "B": pd.Categorical(["Low", "Medium", "High", "Low"]),
            "C": [10, 20, 30, 40],
        }
    )

    new_cols = ["A1", "B[T.Medium]", "A1:B[T.High]", "C"]
    updated_cols = update_factor_names(new_cols, design_matrix)

    # A1 should be mapped to A because A has 2 levels
    assert updated_cols[0] == "A"
    assert "B" in updated_cols[1]
    assert "A*B" in updated_cols[2]
    assert updated_cols[3] == "C"


def test_fit_regression_model() -> None:
    df = pd.DataFrame(
        {
            "Var1": [1.0, -1.0, 1.0, -1.0, 0.0, 0.0],
            "Var2": [1.0, 1.0, -1.0, -1.0, 0.0, 0.0],
            "Response": [12.0, 8.0, 10.0, 6.0, 9.0, 9.2],
        }
    )

    res = fit_regression_model(df, "Response ~ Var1 + Var2")
    assert "coefficients" in res
    assert "anova" in res
    assert res["r_squared"] > 0.8
    assert len(res["fitted_values"]) == 6
    assert len(res["residuals"]) == 6
