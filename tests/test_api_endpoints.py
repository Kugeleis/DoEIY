from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_read_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello from DoEIY FastAPI rewrite!"}


def test_api_generate_design() -> None:
    # Full Factorial request
    payload = {
        "design_type": "Full Factorial",
        "factors": [
            {"name": "Temp", "type": "Continuous", "levels": "100, 200"},
            {"name": "Pres", "type": "Continuous", "levels": "1, 2, 3"},
        ],
    }
    response = client.post("/api/design/generate", json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    # Full factorial 2 x 3 = 6 runs
    assert len(res_data["data"]) == 6
    assert "Temp" in res_data["data"][0]
    assert "Pres" in res_data["data"][0]


def test_api_fit_regression_and_predict() -> None:
    # Fit regression model
    df_data = [
        {"Var1": 1.0, "Var2": 1.0, "Response": 12.0},
        {"Var1": -1.0, "Var2": 1.0, "Response": 8.0},
        {"Var1": 1.0, "Var2": -1.0, "Response": 10.0},
        {"Var1": -1.0, "Var2": -1.0, "Response": 6.0},
        {"Var1": 0.0, "Var2": 0.0, "Response": 9.0},
        {"Var1": 0.0, "Var2": 0.0, "Response": 9.2},
    ]
    fit_payload = {"data": df_data, "formula": "Response ~ Var1 + Var2"}
    response = client.post("/api/analysis/fit", json=fit_payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    assert "coefficients" in res_data
    assert "anova" in res_data

    # Predict response using the fit coefficients
    coefs = res_data["coefficients"]
    pred_payload = {
        "coefficients": [{"term": c["term"], "estimate": c["estimate"]} for c in coefs],
        "factors": {"Var1": 0.5, "Var2": -0.5},
    }
    pred_response = client.post("/api/analysis/predict", json=pred_payload)
    assert pred_response.status_code == 200
    pred_data = pred_response.json()
    assert pred_data["status"] == "success"
    assert pred_data["prediction"] > 8.0


def test_api_optimize() -> None:
    df_data = [
        {"Var1": 1.0, "Var2": 1.0, "Response": 12.0},
        {"Var1": -1.0, "Var2": 1.0, "Response": 8.0},
        {"Var1": 1.0, "Var2": -1.0, "Response": 10.0},
        {"Var1": -1.0, "Var2": -1.0, "Response": 6.0},
        {"Var1": 0.0, "Var2": 0.0, "Response": 9.0},
        {"Var1": 0.0, "Var2": 0.0, "Response": 9.2},
    ]
    opt_payload = {
        "data": df_data,
        "factor_types": {"Var1": "Continuous", "Var2": "Continuous"},
        "opt_type": "Maximize",
        "formula": "Response ~ Var1 + Var2",
    }
    response = client.post("/api/analysis/optimize", json=opt_payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    assert res_data["optimal_factors"]["Var1"] > 0.0
    assert res_data["optimal_response"] > 11.0
