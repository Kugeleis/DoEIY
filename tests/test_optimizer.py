import numpy as np
import pandas as pd
import pytest
import statsmodels.formula.api as smf

from app.engine.optimizer import objective_value, optimize_model


def test_objective_value() -> None:
    # Maximize -> returns negative of prediction
    assert objective_value(5.0, "Maximize") == -5.0
    assert objective_value(-3.0, "Maximize") == 3.0

    # Minimize -> returns prediction unchanged
    assert objective_value(5.0, "Minimize") == 5.0
    assert objective_value(-3.0, "Minimize") == -3.0

    # Find Target -> returns squared difference
    assert objective_value(8.0, "Find Target", target=10.0) == 4.0
    assert objective_value(12.0, "Find Target", target=10.0) == 4.0

    # Other types -> return prediction unchanged
    assert objective_value(5.0, "UnknownType") == 5.0


def test_objective_value_errors() -> None:
    with pytest.raises(ValueError):
        objective_value(5.0, "Find Target")
    with pytest.raises(ValueError):
        objective_value(5.0, "Find Target", target=None)


def test_optimize_model() -> None:
    df = pd.DataFrame(
        {
            "Var1": [1.0, -1.0, 1.0, -1.0, 0.0, 0.0],
            "Var2": [1.0, 1.0, -1.0, -1.0, 0.0, 0.0],
            "Response": [12.0, 8.0, 10.0, 6.0, 9.0, 9.2],
        }
    )

    # Fit statsmodels model
    model = smf.ols("Response ~ Var1 + Var2", data=df).fit()

    factor_types = {"Var1": "Continuous", "Var2": "Continuous"}

    # Optimize to Maximize Response
    res = optimize_model(model, df, factor_types, "Maximize")
    assert res["success"] is True
    assert res["best_factors"]["Var1"] > 0.0
    assert res["best_factors"]["Var2"] > 0.0
    assert res["best_pred"] > 11.0

    # Optimize to Minimize Response
    res_min = optimize_model(model, df, factor_types, "Minimize")
    assert res_min["success"] is True
    assert res_min["best_factors"]["Var1"] < 0.0
    assert res_min["best_factors"]["Var2"] < 0.0
    assert res_min["best_pred"] < 7.0

    # Optimize to Find Target Response = 9.0
    res_tar = optimize_model(model, df, factor_types, "Find Target", target_response=9.0)
    assert res_tar["success"] is True
    assert abs(res_tar["best_pred"] - 9.0) < 0.5


def test_optimize_model_categorical() -> None:
    df = pd.DataFrame(
        {
            "Var1": [1.0, -1.0, 1.0, -1.0, 0.0, 0.0],
            "Var2": pd.Categorical(["Low", "Low", "High", "High", "Low", "High"]),
            "Response": [12.0, 8.0, 15.0, 11.0, 10.0, 13.0],
        }
    )
    model = smf.ols("Response ~ Var1 + C(Var2)", data=df).fit()
    factor_types = {"Var1": "Continuous", "Var2": "Categorical"}

    res = optimize_model(model, df, factor_types, "Maximize")
    assert res["success"] is True
    assert res["best_factors"]["Var2"] == "High"
    assert res["best_factors"]["Var1"] > 0.0


def test_optimize_model_no_continuous() -> None:
    df = pd.DataFrame(
        {
            "Var1": pd.Categorical(["Low", "Low", "High", "High"]),
            "Var2": [1, 2, 1, 2],
            "Response": [10.0, 12.0, 14.0, 18.0],
        }
    )
    model = smf.ols("Response ~ C(Var1) + Var2", data=df).fit()
    factor_types = {"Var1": "Categorical", "Var2": "Discrete"}

    res = optimize_model(model, df, factor_types, "Maximize")
    assert res["success"] is True
    assert res["best_factors"]["Var1"] == "High"
    assert res["best_factors"]["Var2"] == 2


def test_optimize_model_many_combos() -> None:
    # 8 categorical variables with 3 levels each -> 3^8 = 6561 combinations (> 5000)
    df_data = {}
    factor_types = {}
    for i in range(8):
        vname = f"Var{i + 1}"
        df_data[vname] = pd.Categorical(["A", "B", "C"] * 3)
        factor_types[vname] = "Categorical"
    df_data["Response"] = np.random.normal(10, 1, 9)
    df = pd.DataFrame(df_data)

    model = smf.ols("Response ~ Var1", data=df).fit()
    res = optimize_model(model, df, factor_types, "Maximize")
    assert res["success"] is True
