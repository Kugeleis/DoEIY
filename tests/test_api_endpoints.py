from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_read_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert b"DoEIY" in response.content


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


def test_api_generate_other_designs() -> None:
    # 1. Plackett-Burman
    payload_pb = {
        "design_type": "Plackett-Burman",
        "factors": [{"name": f"F{i}", "type": "Continuous", "levels": "-1, 1"} for i in range(5)],
    }
    response = client.post("/api/design/generate", json=payload_pb)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # 2. Fractional Factorial with blocks
    payload_ff = {
        "design_type": "Fractional Factorial",
        "factors": [{"name": f"F{i}", "type": "Continuous", "levels": "-1, 1"} for i in range(4)],
        "num_runs": 8,
        "num_blocks": 2,
    }
    response = client.post("/api/design/generate", json=payload_ff)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # 3. Latin Hypercube
    payload_lh = {
        "design_type": "Latin Hypercube Sampling",
        "factors": [
            {"name": "X1", "type": "Continuous", "levels": "0, 10"},
            {"name": "X2", "type": "Continuous", "levels": "5, 15"},
        ],
        "num_runs": 10,
    }
    response = client.post("/api/design/generate", json=payload_lh)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # 4. Box-Behnken
    payload_bb = {
        "design_type": "Box-Behnken",
        "factors": [
            {"name": "X1", "type": "Continuous", "levels": "0, 5, 10"},
            {"name": "X2", "type": "Continuous", "levels": "1, 2, 3"},
            {"name": "X3", "type": "Continuous", "levels": "10, 20, 30"},
        ],
    }
    response = client.post("/api/design/generate", json=payload_bb)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # 5. Central Composite
    payload_cc = {
        "design_type": "Central Composite",
        "factors": [
            {"name": "X1", "type": "Continuous", "levels": "0, 10"},
            {"name": "X2", "type": "Continuous", "levels": "5, 15"},
        ],
    }
    response = client.post("/api/design/generate", json=payload_cc)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # 6. D-Optimal
    payload_do = {
        "design_type": "D-Optimal",
        "factors": [
            {"name": "X1", "type": "Continuous", "levels": "0, 5, 10"},
            {"name": "X2", "type": "Categorical", "levels": "Low, Medium, High"},
        ],
        "num_runs": 6,
    }
    response = client.post("/api/design/generate", json=payload_do)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_api_augment_design() -> None:
    df_data = [
        {"X1": 0.0, "X2": "Low"},
        {"X1": 10.0, "X2": "High"},
        {"X1": 5.0, "X2": "Low"},
    ]
    payload_aug = {
        "existing_design": df_data,
        "factors": [
            {"name": "X1", "type": "Continuous", "levels": "0, 5, 10"},
            {"name": "X2", "type": "Categorical", "levels": "Low, Medium, High"},
        ],
        "nruns": 3,
        "components": ["X1", "X2"],
    }
    response = client.post("/api/design/augment", json=payload_aug)
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "success"
    assert len(res["data"]) == 6  # 3 original + 3 augmented


def test_api_errors_and_exceptions() -> None:
    # 1. Invalid design type
    payload_err1 = {
        "design_type": "Invalid Design Type",
        "factors": [{"name": "X1", "type": "Continuous", "levels": "0, 10"}],
    }
    response = client.post("/api/design/generate", json=payload_err1)
    assert response.status_code == 400

    # 2. Invalid formula in fit
    fit_payload = {"data": [{"X1": 1.0, "Response": 10.0}], "formula": "Response ~ InvalidCol"}
    response = client.post("/api/analysis/fit", json=fit_payload)
    assert response.status_code == 400

    # 3. Invalid optimize formula
    opt_payload = {
        "data": [{"X1": 1.0, "Response": 10.0}],
        "factor_types": {"X1": "Continuous"},
        "opt_type": "Maximize",
        "formula": "Response ~ InvalidCol",
    }
    response = client.post("/api/analysis/optimize", json=opt_payload)
    assert response.status_code == 400

    # 4. Invalid augment payload (runtime exception)
    payload_err4 = {"existing_design": [], "factors": [], "components": [], "nruns": -1}
    response = client.post("/api/design/augment", json=payload_err4)
    assert response.status_code == 500

    # 5. Missing Fractional runs/blocks
    payload_err5 = {
        "design_type": "Fractional Factorial",
        "factors": [{"name": "F1", "type": "Continuous", "levels": "-1, 1"}],
    }
    response = client.post("/api/design/generate", json=payload_err5)
    assert response.status_code == 400

    # 6. Missing Latin Hypercube runs
    payload_err6 = {
        "design_type": "Latin Hypercube Sampling",
        "factors": [{"name": "F1", "type": "Continuous", "levels": "0, 10"}],
    }
    response = client.post("/api/design/generate", json=payload_err6)
    assert response.status_code == 400

    # 7. Missing D-Optimal runs
    payload_err7 = {"design_type": "D-Optimal", "factors": [{"name": "F1", "type": "Continuous", "levels": "0, 10"}]}
    response = client.post("/api/design/generate", json=payload_err7)
    assert response.status_code == 400

    # 8. evaluate_term & parse_levels edge cases
    from app.main import evaluate_term, parse_levels

    assert evaluate_term("X1", {"X1": "invalid"}) == 0.0
    assert evaluate_term("X1**invalid", {"X1": 2.0}) == 0.0
    assert evaluate_term("C(X1)[T.Medium]", {"X1": "Medium"}) == 1.0
    assert evaluate_term("C(X1)[T.Medium]", {"X1": "Low"}) == 0.0
    assert parse_levels("a, b", "Continuous") == ["a", "b"]
    assert parse_levels([1, 2], "Continuous") == [1, 2]
