import re
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.engine.design_generators import (
    generate_box_behnken,
    generate_central_composite,
    generate_d_optimal,
    generate_d_optimal_augment,
    generate_fractional_factorial,
    generate_full_factorial,
    generate_latin_hypercube,
    generate_plackett_burman,
)
from app.engine.optimizer import optimize_model
from app.engine.stats_engine import fit_regression_model, update_factor_names

app = FastAPI(title="DoEIY - Design of Experiments API")


# --- Schemas ---
class FactorInput(BaseModel):
    name: str
    type: str  # Continuous, Discrete, Categorical
    levels: list[Any] | str  # list of level values or comma-separated string


class DesignRequest(BaseModel):
    design_type: str
    factors: list[FactorInput]
    num_runs: int | None = None
    num_blocks: int | None = None


class AugmentRequest(BaseModel):
    existing_design: list[dict[str, Any]]
    factors: list[FactorInput]
    components: list[str]
    nruns: int
    randomize: bool = True


class FitRequest(BaseModel):
    data: list[dict[str, Any]]
    formula: str


class PredictRequest(BaseModel):
    coefficients: list[dict[str, Any]]  # [{"term": "Intercept", "estimate": 9.0}, ...]
    factors: dict[str, Any]  # {"Var1": 0.5, "Var2": "Medium"}


class OptimizeRequest(BaseModel):
    data: list[dict[str, Any]]
    factor_types: dict[str, str]
    opt_type: str  # Maximize, Minimize, Find Target
    target_response: float | None = None
    formula: str


# --- Helpers ---
def parse_levels(levels: list[Any] | str, ftype: str) -> list[Any]:
    if isinstance(levels, str):
        parts = [p.strip() for p in levels.split(",")]
        if ftype == "Continuous" or ftype == "Discrete":
            try:
                return [float(p) for p in parts]
            except ValueError:
                return parts
        return parts
    return levels


def evaluate_term(term: str, factors: dict[str, Any]) -> float:
    """
    Statelessly evaluates a model term value given the factor values.
    """
    if term == "Intercept":
        return 1.0

    # Handle patsy categorical level syntax: e.g., C(Var2)[T.Medium] or Var2[T.Medium]
    match = re.match(r"(?:C\()?([a-zA-Z0-9_]+)\)?\[T\.(.*?)\]", term)
    if match:
        col, level = match.groups()
        return 1.0 if str(factors.get(col)) == level else 0.0

    # Standard interaction terms containing :
    if ":" in term:
        parts = term.split(":")
        val = 1.0
        for p in parts:
            val *= evaluate_term(p, factors)
        return val

    # Quadratic/Power terms, e.g. I(Var1**2) or Var1**2
    clean_term = re.sub(r"I\((.*?)\)", r"\1", term)
    # Check if this is a raw variable name
    if clean_term in factors:
        try:
            return float(factors[clean_term])
        except (ValueError, TypeError):
            return 0.0

    # Evaluate mathematical expressions like Var1**2
    try:
        # Evaluate expression inside factors namespace
        val = eval(clean_term, {}, factors)
        return float(val)
    except Exception:
        return 0.0


# --- Endpoints ---
@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Hello from DoEIY FastAPI rewrite!"}


@app.post("/api/design/generate")
def api_generate_design(req: DesignRequest) -> dict[str, Any]:
    n_factors = len(req.factors)
    factor_names = [f.name for f in req.factors]

    # Convert factors schema to format needed by generators
    levels_list = []
    for f in req.factors:
        levels_list.append(parse_levels(f.levels, f.type))

    try:
        if req.design_type == "Plackett-Burman":
            df = generate_plackett_burman(n_factors)
        elif req.design_type == "Full Factorial":
            levels_count = [len(lv) for lv in levels_list]
            df = generate_full_factorial(levels_count)
        elif req.design_type == "Fractional Factorial":
            if req.num_runs is None or req.num_blocks is None:
                raise HTTPException(status_code=400, detail="num_runs and num_blocks are required.")
            res = generate_fractional_factorial(req.num_runs, n_factors, req.num_blocks)
            df = res["Design"]
            resolution = res["Resolution"]
        elif req.design_type == "Box-Behnken":
            df = generate_box_behnken(n_factors)
        elif req.design_type == "Central Composite":
            # Default to Circumscribed if not specified
            df = generate_central_composite(n_factors, "Circumscribed")
        elif req.design_type == "Latin Hypercube Sampling":
            if req.num_runs is None:
                raise HTTPException(status_code=400, detail="num_runs is required.")
            df = generate_latin_hypercube(n_factors, req.num_runs)
        elif req.design_type == "D-Optimal":
            if req.num_runs is None:
                raise HTTPException(status_code=400, detail="num_runs is required.")
            # For D-Optimal, components are passed or we use main effects
            components = [f"Var{i + 1}" for i in range(n_factors)]
            factor_types = [f.type for f in req.factors]
            levels_count = [len(lv) for lv in levels_list]
            df = generate_d_optimal(levels_count, components, factor_types, req.num_runs)
        else:
            raise HTTPException(status_code=400, detail="Unknown design type.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    # Re-apply factor level scaling/mapping
    # Scaled continuous factors map [-1, 1] to original limits
    for i, f in enumerate(req.factors):
        col_name = f"Var{i + 1}"
        target_name = f.name
        levels = levels_list[i]

        if col_name in df.columns:
            col = df[col_name]
            if f.type == "Continuous":
                # Scale from [-1, 1] to [min, max]
                cmin = min(levels)
                cmax = max(levels)
                if cmin == cmax:
                    df[target_name] = cmin
                else:
                    df[target_name] = ((col + 1.0) / 2.0) * (cmax - cmin) + cmin
            elif f.type == "Discrete":
                # Scale and snap to nearest level value
                cmin = min(levels)
                cmax = max(levels)
                if cmin == cmax:
                    df[target_name] = cmin
                else:
                    scaled = ((col + 1.0) / 2.0) * (cmax - cmin) + cmin
                    df[target_name] = scaled.apply(lambda v, lv=levels: lv[np.argmin(np.abs(np.array(lv) - v))])
            elif f.type == "Categorical":
                # Match 1-indexed integers to levels list
                indices = col.astype(int) - 1
                df[target_name] = [levels[idx] for idx in indices]

            if target_name != col_name:
                df.drop(columns=[col_name], inplace=True)

    # Re-order and include Block if present
    if "Block" in df.columns:
        cols = factor_names + ["Block"]
        df = df[cols]
    else:
        df = df[factor_names]

    response_data = df.to_dict(orient="records")
    return {
        "status": "success",
        "data": response_data,
        "resolution": resolution if req.design_type == "Fractional Factorial" else None,
    }


@app.post("/api/design/augment")
def api_augment_design(req: AugmentRequest) -> dict[str, Any]:
    df_existing = pd.DataFrame(req.existing_design)
    [f.name for f in req.factors]

    levels_dict = {}
    factor_types_dict = {}
    for f in req.factors:
        levels_dict[f.name] = len(parse_levels(f.levels, f.type))
        factor_types_dict[f.name] = f.type

    try:
        df_aug = generate_d_optimal_augment(
            df_existing, levels_dict, req.components, factor_types_dict, req.nruns, req.randomize
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"status": "success", "data": df_aug.to_dict(orient="records")}


@app.post("/api/analysis/fit")
def api_fit_regression(req: FitRequest) -> dict[str, Any]:
    df = pd.DataFrame(req.data)
    try:
        res = fit_regression_model(df, req.formula)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Formula fitting failed: {str(e)}") from e

    # Clean coefficients and ANOVA names for UI presentation
    coefficients_cleaned = []
    for c in res["coefficients"]:
        coefficients_cleaned.append({**c, "term_clean": update_factor_names([c["term"]], df)[0]})

    anova_cleaned = []
    for a in res["anova"]:
        anova_cleaned.append({**a, "term_clean": update_factor_names([a["term"]], df)[0]})

    return {
        "status": "success",
        "coefficients": coefficients_cleaned,
        "anova": anova_cleaned,
        "r_squared": res["r_squared"],
        "adj_r_squared": res["adj_r_squared"],
        "fitted_values": res["fitted_values"],
        "residuals": res["residuals"],
    }


@app.post("/api/analysis/predict")
def api_predict_response(req: PredictRequest) -> dict[str, Any]:
    prediction = 0.0
    for coef in req.coefficients:
        term = coef["term"]
        estimate = coef["estimate"]
        term_val = evaluate_term(term, req.factors)
        prediction += estimate * term_val

    return {"status": "success", "prediction": prediction}


@app.post("/api/analysis/optimize")
def api_optimize_response(req: OptimizeRequest) -> dict[str, Any]:
    df = pd.DataFrame(req.data)
    try:
        fit = fit_regression_model(df, req.formula)
        model = fit["model_object"]
        res = optimize_model(model, df, req.factor_types, req.opt_type, req.target_response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"status": "success", "optimal_factors": res["best_factors"], "optimal_response": res["best_pred"]}
