import itertools
import random
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize


def objective_value(pred: float, opt_type: str, target: float | None = None) -> float:
    """
    Standardizes predictions to a minimization objective.
    """
    if opt_type == "Maximize":
        return -pred
    elif opt_type == "Minimize":
        return pred
    elif opt_type == "Find Target":
        if target is None:
            raise ValueError("Target response is required.")
        return (pred - target) ** 2
    return pred


def optimize_model(
    model: Any,
    design_matrix: pd.DataFrame,
    factor_types: dict[str, str],
    opt_type: str,
    target_response: float | None = None,
) -> dict[str, Any]:
    """
    Performs global/local grid-search and continuous minimization optimization.
    """
    # 1. Classify variables
    continuous_vars = []
    noncont_vars = []

    for col in design_matrix.columns:
        if col == "Response" or col == "Block":
            continue
        ftype = factor_types.get(col, "Continuous")
        if ftype == "Continuous":
            continuous_vars.append(col)
        else:
            noncont_vars.append(col)

    # 2. Build grid for non-continuous variables
    choices_list = {}
    for v in noncont_vars:
        colv = design_matrix[v]
        # Get unique values sorted
        if isinstance(colv.dtype, pd.CategoricalDtype):
            choices_list[v] = list(colv.cat.categories)
        else:
            choices_list[v] = sorted(colv.unique())

    if choices_list:
        keys = list(choices_list.keys())
        combos = list(itertools.product(*(choices_list[k] for k in keys)))
        combo_grid = [dict(zip(keys, c, strict=False)) for c in combos]
    else:
        combo_grid = [{}]

    # Cap combinations at 5000
    if len(combo_grid) > 5000:
        random.seed(1)
        combo_grid = random.sample(combo_grid, 5000)

    # 3. Setup continuous bounds and start values
    cont_start = []
    bounds = []
    for v in continuous_vars:
        colv = pd.to_numeric(design_matrix[v])
        cmin = float(colv.min())
        cmax = float(colv.max())
        start = float(colv.mean())
        cont_start.append(start)
        bounds.append((cmin, cmax))

    best_obj = float("inf")
    best_factors = {}
    best_pred = 0.0

    # 4. Loop combinations
    for fixed_vars in combo_grid:

        def fn(par: np.ndarray, fv: dict[str, Any] = fixed_vars) -> float:
            test_row = dict(zip(continuous_vars, par, strict=False))
            # Merge fixed vars
            full_row = {**test_row, **fv}
            df = pd.DataFrame([full_row])

            # Predict
            pred = float(model.predict(df)[0])
            return objective_value(pred, opt_type, target=target_response)

        if continuous_vars:
            res = minimize(
                fn,
                np.array(cont_start),
                method="L-BFGS-B",
                bounds=bounds,
                options={"maxiter": 200},
            )
            sol_cont = dict(zip(continuous_vars, res.x, strict=False))
            full_row = {**sol_cont, **fixed_vars}
        else:
            full_row = fixed_vars

        df_final = pd.DataFrame([full_row])
        pred_val = float(model.predict(df_final)[0])
        obj_val = objective_value(pred_val, opt_type, target=target_response)

        if obj_val < best_obj:
            best_obj = obj_val
            best_factors = full_row
            best_pred = pred_val

    return {
        "success": True,
        "best_obj": best_obj,
        "best_factors": best_factors,
        "best_pred": best_pred,
    }
