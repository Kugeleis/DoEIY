import numpy as np
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_complete_doe_workflow_e2e() -> None:
    # -------------------------------------------------------------
    # Step 1: Generate a Central Composite Design (CCD)
    # -------------------------------------------------------------
    generate_payload = {
        "design_type": "Central Composite",
        "factors": [
            {"name": "Temperature", "type": "Continuous", "levels": "150, 200"},
            {"name": "Pressure", "type": "Continuous", "levels": "10, 30"},
        ],
    }

    gen_response = client.post("/api/design/generate", json=generate_payload)
    assert gen_response.status_code == 200
    gen_data = gen_response.json()
    assert gen_data["status"] == "success"

    design_runs = gen_data["data"]
    # CCD for 2 factors typically has 4 factorial runs + axial + center runs = 14 runs
    assert len(design_runs) > 0
    assert "Temperature" in design_runs[0]
    assert "Pressure" in design_runs[0]

    # -------------------------------------------------------------
    # Step 2: Simulate adding experimental responses
    # -------------------------------------------------------------
    # We will simulate a response model: y = 50 + 0.5 * Temp - 0.2 * Pres + error
    for run in design_runs:
        temp = float(run["Temperature"])
        pres = float(run["Pressure"])
        # Simulated response equation
        run["Response"] = 50.0 + 0.5 * (temp - 175.0) - 0.2 * (pres - 20.0) + np.random.normal(0, 0.1)

    # -------------------------------------------------------------
    # Step 3: Fit an OLS model with quadratic and interaction terms
    # -------------------------------------------------------------
    # Formula in Patsy/FastAPI format: Response ~ Temperature + Pressure + I(Temperature**2) + Temperature:Pressure
    fit_payload = {
        "data": design_runs,
        "formula": "Response ~ Temperature + Pressure + I(Temperature**2) + Temperature:Pressure",
    }
    fit_response = client.post("/api/analysis/fit", json=fit_payload)
    assert fit_response.status_code == 200
    fit_data = fit_response.json()
    assert fit_data["status"] == "success"
    assert "coefficients" in fit_data
    assert "anova" in fit_data
    assert fit_data["r_squared"] > 0.9

    coefficients = fit_data["coefficients"]

    # -------------------------------------------------------------
    # Step 4: Predict response at new coordinates
    # -------------------------------------------------------------
    predict_payload = {
        "coefficients": [{"term": c["term"], "estimate": c["estimate"]} for c in coefficients],
        "factors": {"Temperature": 190.0, "Pressure": 15.0},
    }
    pred_response = client.post("/api/analysis/predict", json=predict_payload)
    assert pred_response.status_code == 200
    pred_data = pred_response.json()
    assert pred_data["status"] == "success"

    # Expected value around: 50 + 0.5*(190-175) - 0.2*(15-20) = 50 + 7.5 + 1.0 = 58.5
    assert 55.0 <= pred_data["prediction"] <= 62.0

    # -------------------------------------------------------------
    # Step 5: Optimize to Maximize Response
    # -------------------------------------------------------------
    optimize_payload = {
        "data": design_runs,
        "factor_types": {"Temperature": "Continuous", "Pressure": "Continuous"},
        "opt_type": "Maximize",
        "formula": "Response ~ Temperature + Pressure + I(Temperature**2) + Temperature:Pressure",
    }
    opt_response = client.post("/api/analysis/optimize", json=optimize_payload)
    assert opt_response.status_code == 200
    opt_data = opt_response.json()
    assert opt_data["status"] == "success"

    # Maximum should be at high temperature (200) and low pressure (10)
    assert opt_data["optimal_factors"]["Temperature"] > 185.0
    assert opt_data["optimal_factors"]["Pressure"] < 15.0
    assert opt_data["optimal_response"] > 58.0

    # -------------------------------------------------------------
    # Step 6: Augment the existing design with new D-optimal runs
    # -------------------------------------------------------------
    augment_payload = {
        "existing_design": design_runs,
        "factors": [
            {"name": "Temperature", "type": "Continuous", "levels": "150, 200"},
            {"name": "Pressure", "type": "Continuous", "levels": "10, 30"},
        ],
        "components": ["Temperature", "Pressure", "I(Temperature**2)", "Temperature:Pressure"],
        "nruns": 4,
        "randomize": False,
    }
    aug_response = client.post("/api/design/augment", json=augment_payload)
    assert aug_response.status_code == 200
    aug_data = aug_response.json()
    assert aug_data["status"] == "success"
    # Augmented design should have original length + 4 new runs
    assert len(aug_data["data"]) == len(design_runs) + 4
