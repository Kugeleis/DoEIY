import re
from typing import Any

import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf


def classify_terms(term: str) -> int:
    """
    Classifies a term's interaction order.
    E.g., "A" -> 1, "A:B" -> 2.
    """
    if not term or term.strip() == "":
        return 0
    # Clean patsy power wraps like I(A**2)
    clean = re.sub(r"I\((.*?)\*\*.*?\)", r"\1", term)
    return len(clean.split(":")) if ":" in clean else 1


def factor_degree(fname: str, components: list[str]) -> int:
    """
    Finds the maximum polynomial degree of a factor in a list of model components.
    """
    deg = 1
    for comp in components:
        # Check for power term
        if f"{fname}:{fname}:{fname}" in comp:
            deg = max(deg, 3)
        elif f"{fname}:{fname}" in comp or f"I({fname}**2)" in comp or f"I({fname}^2)" in comp:
            deg = max(deg, 2)
    return deg


def fix_component(term: str) -> str:
    """
    Formats component term for Python statsmodels/patsy formulas.
    E.g., "x1:x1" -> "I(x1**2)", "x1:x1:x1" -> "I(x1**3)".
    """
    term = term.strip()
    if ":" in term:
        parts = term.split(":")
        unique_parts = set(parts)
        if len(unique_parts) == 1:
            # Quadratic or higher order of single variable
            var = list(unique_parts)[0]
            power = len(parts)
            return f"I({var}**{power})"
    return term


def term_params(term: str, factor_info: dict[str, Any]) -> int:
    """
    Calculates parameter count for a term based on factor types and levels.
    """
    if not term:
        return 0
    # Strip patsy formula syntax
    clean = re.sub(r"I\((.*?)\*\*.*?\)", r"\1", term)
    parts = clean.split(":")

    params = 1
    for p in parts:
        p = p.strip()
        if p in factor_info:
            ftype = factor_info[p].get("type", "Continuous")
            levels = factor_info[p].get("levels", [])
            if ftype in ["Categorical", "Discrete"]:
                k = len(levels)
                params *= max(1, k - 1)
        else:
            # Default to 1 parameter (continuous)
            params *= 1
    return params


def validate_num_runs(num_runs: str | int | float, min_runs: int, max_runs: int) -> dict[str, Any]:
    """
    Validates input run count.
    """
    # 1. Check type
    try:
        val = float(num_runs)
    except (ValueError, TypeError):
        return {"valid": False, "message": "must be a single numeric integer"}

    # 2. Check if integer
    if not val.is_integer():
        return {"valid": False, "message": "must be an integer"}

    val_int = int(val)

    # 3. Check greater than zero
    if val_int <= 0:
        return {"valid": False, "message": "must be greater than zero"}

    # 4. Check bounds
    if val_int < min_runs or val_int > max_runs:
        return {"valid": False, "message": f"must be within the minumum and maximum limits ({min_runs} to {max_runs})"}

    return {"valid": True, "message": None, "value": val_int}


def transform_term(term: str) -> str:
    """
    Transforms term layout to patsy standard.
    E.g., "A * A" -> "I(A**2)", "A * B" -> "A:B".
    """
    term = term.strip()
    if "*" in term:
        parts = [p.strip() for p in term.split("*")]
        unique = set(parts)
        if len(unique) == 1:
            return f"I({list(unique)[0]}**{len(parts)})"
        return ":".join(parts)
    return term


def update_factor_names(terms: list[str], design_matrix: pd.DataFrame) -> list[str]:
    """
    Cleans up parameter names returned by statsmodels OLS model to match
    original design matrix factor names (for Categorical levels handling).
    """
    cleaned = []
    # Extract factor columns
    orig_cols = list(design_matrix.columns)

    for term in terms:
        # Split by patsy interaction symbol ":"
        parts = term.split(":")
        new_parts = []
        for part in parts:
            part_clean = part.strip()
            # Clean statsmodels categorical wraps like C(B)[T.Medium] or B[T.Medium]
            for col in orig_cols:
                part_clean = re.sub(rf"C\({col}\)\[T\..*?\]", col, part_clean)
                part_clean = re.sub(rf"{col}\[T\..*?\]", col, part_clean)

                if part_clean == f"{col}1" and len(design_matrix[col].unique()) == 2:
                    part_clean = col
            new_parts.append(part_clean)

        t_clean = ":".join(new_parts)

        # Replace patsy I(X**2) format back to original X*X representation
        t_clean = re.sub(r"I\((.*?)\*\*2\)", r"\1*\1", t_clean)
        t_clean = re.sub(r"I\((.*?)\*\*3\)", r"\1*\1*\1", t_clean)

        # Replace patsy interaction symbol : with R-like *
        t_clean = t_clean.replace(":", "*")

        cleaned.append(t_clean)

    return cleaned


def fit_regression_model(data: pd.DataFrame, formula: str) -> dict[str, Any]:
    """
    Fits an OLS model to the design matrix data.
    Formula example: "Response ~ Var1 + Var2 + I(Var1**2) + Var1:Var2"
    """
    # Statsmodels OLS
    model = smf.ols(formula, data=data).fit()
    anova_table = sm.stats.anova_lm(model, typ=1)

    coefficients = []
    for name in model.params.index:
        coefficients.append(
            {
                "term": name,
                "estimate": model.params[name],
                "std_error": model.bse[name],
                "t_value": model.tvalues[name],
                "p_value": model.pvalues[name],
            }
        )

    anova_rows = []
    for index, row in anova_table.iterrows():
        # Patsy terms matching
        anova_rows.append(
            {
                "term": index,
                "df": int(row["df"]) if not pd.isna(row["df"]) else 0,
                "sum_sq": row["sum_sq"] if not pd.isna(row["sum_sq"]) else 0.0,
                "mean_sq": row["mean_sq"] if not pd.isna(row["mean_sq"]) else 0.0,
                "f_value": row["F"] if not pd.isna(row["F"]) else None,
                "p_value": row["PR(>F)"] if not pd.isna(row["PR(>F)"]) else None,
            }
        )

    # Summary metrics
    return {
        "coefficients": coefficients,
        "anova": anova_rows,
        "r_squared": model.rsquared,
        "adj_r_squared": model.rsquared_adj,
        "fitted_values": model.fittedvalues.tolist(),
        "residuals": model.resid.tolist(),
        "model_object": model,
    }
