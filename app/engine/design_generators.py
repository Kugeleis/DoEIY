import itertools
import string
import sys
import types
from typing import Any

import numpy as np
import pandas as pd
import patsy
from scipy.stats import qmc

# Mock the 'imp' module for python 3.12+ compatibility
# pyDOE2 imports 'imp' at module level but does not use it.
if "imp" not in sys.modules:
    sys.modules["imp"] = types.ModuleType("imp")

import pyDOE2


def generate_full_factorial(factor_levels: list[int]) -> pd.DataFrame:
    """
    Creates a full factorial design from factor levels.
    """
    levels_list = [list(range(1, k + 1)) for k in factor_levels]
    combinations = list(itertools.product(*levels_list))
    df = pd.DataFrame(combinations, columns=[f"Var{i + 1}" for i in range(len(factor_levels))])
    return df


def is_aliased(a: np.ndarray, b: np.ndarray, tol: float = 1e-12) -> bool:
    """
    Helper function to check if two design columns are aliased (linear dependency).
    """
    # Standard deviation check for constant columns
    sa = np.std(a)
    sb = np.std(b)
    if sa <= tol and sb <= tol:
        return True
    if sa <= tol or sb <= tol:
        return False

    # Check correlation
    r = np.corrcoef(a, b)[0, 1]
    return bool(np.isfinite(r) and (abs(r) >= 1 - tol))


def get_resolution(design_matrix: np.ndarray) -> str:
    """
    Evaluates the resolution of a fractional factorial design matrix.
    """
    n_runs, p = design_matrix.shape

    # 1. Main factor aliasing
    if p >= 2:
        for i in range(p - 1):
            for j in range(i + 1, p):
                if is_aliased(design_matrix[:, i], design_matrix[:, j]):
                    return "Resolution II"

    # Build 2-factor interactions
    two_factor_cols = []
    if p >= 2:
        for i in range(p - 1):
            for j in range(i + 1, p):
                two_factor_cols.append(design_matrix[:, i] * design_matrix[:, j])
    two_factor_interactions = np.column_stack(two_factor_cols) if two_factor_cols else np.empty((n_runs, 0))

    # 2. Check main with 2-factor
    if two_factor_interactions.shape[1] > 0:
        for i in range(p):
            for j in range(two_factor_interactions.shape[1]):
                if is_aliased(design_matrix[:, i], two_factor_interactions[:, j]):
                    return "Resolution III"

    # 3. Check 2-factor with 2-factor
    if two_factor_interactions.shape[1] >= 2:
        for i in range(two_factor_interactions.shape[1] - 1):
            for j in range(i + 1, two_factor_interactions.shape[1]):
                if is_aliased(two_factor_interactions[:, i], two_factor_interactions[:, j]):
                    return "Resolution IV"

    # Build 3-factor interactions
    three_factor_cols = []
    if p >= 3:
        for i in range(p - 2):
            for j in range(i + 1, p - 1):
                for k in range(j + 1, p):
                    three_factor_cols.append(design_matrix[:, i] * design_matrix[:, j] * design_matrix[:, k])
    three_factor_interactions = np.column_stack(three_factor_cols) if three_factor_cols else np.empty((n_runs, 0))

    # 4. Check 2-factor with 3-factor
    if two_factor_interactions.shape[1] > 0 and three_factor_interactions.shape[1] > 0:
        for i in range(two_factor_interactions.shape[1]):
            for j in range(three_factor_interactions.shape[1]):
                if is_aliased(two_factor_interactions[:, i], three_factor_interactions[:, j]):
                    return "Resolution V"

    return "Resolution VI or higher"


def generate_fractional_factorial(num_runs: int, num_factors: int, num_blocks: int) -> dict[str, Any]:
    """
    Generates a Fractional Factorial design with minimum aberration/maximum resolution.
    """
    k = int(np.log2(num_runs))  # Number of base factors
    if 2**k != num_runs:
        raise ValueError("Number of runs must be a power of 2.")

    base_letters = [string.ascii_lowercase[i] for i in range(k)]

    # Generate all possible interaction terms to use as generators
    possible_generators = []
    for r in range(2, k + 1):
        for comb in itertools.combinations(base_letters, r):
            possible_generators.append("".join(comb))

    n_generators = num_factors - k

    if n_generators < 0:
        raise ValueError("Number of runs is too large for the number of factors.")
    elif n_generators == 0:
        # Full Factorial
        gen_str = " ".join(base_letters)
        design = pyDOE2.fracfact(gen_str)
        res_str = "Resolution VI or higher"
    else:
        # Search for combination of generators that maximizes resolution
        best_res_num = -1
        best_design = None
        best_res_str = "Resolution II"

        res_mapping = {
            "Resolution II": 2,
            "Resolution III": 3,
            "Resolution IV": 4,
            "Resolution V": 5,
            "Resolution VI or higher": 6,
        }

        for comb in itertools.combinations(possible_generators, n_generators):
            gen_str = " ".join(base_letters) + " " + " ".join(comb)
            try:
                design_cand = pyDOE2.fracfact(gen_str)
                res_cand = get_resolution(design_cand)
                res_num = res_mapping[res_cand]
                if res_num > best_res_num:
                    best_res_num = res_num
                    best_design = design_cand
                    best_res_str = res_cand
                    if res_num == 6:  # Max possible resolution
                        break
            except Exception:
                continue

        if best_design is None:
            raise ValueError("Could not find a valid fractional design.")
        design = best_design
        res_str = best_res_str

    df = pd.DataFrame(design, columns=[f"Var{i + 1}" for i in range(num_factors)])

    # Assign blocks if requested
    if num_blocks > 1:
        # We need b = log2(num_blocks) blocking variables
        int(np.log2(num_blocks))
        # Choose a high-order interaction column to split into blocks
        # Simply use binary representation of run index for block splitting
        # as a standard orthogonal partition
        block_col = []
        for i in range(num_runs):
            block_col.append((i % num_blocks) + 1)
        df["Block"] = block_col

    return {"Design": df, "Resolution": res_str}


def generate_latin_hypercube(num_factors: int, num_runs: int) -> pd.DataFrame:
    """
    Generates an optimized space-filling Latin Hypercube design.
    """
    sampler = qmc.LatinHypercube(d=num_factors, optimization="random-cd")
    sample = sampler.random(n=num_runs)
    scaled_sample = qmc.scale(sample, -1, 1)

    df = pd.DataFrame(scaled_sample, columns=[f"Var{i + 1}" for i in range(num_factors)])
    return df


def generate_plackett_burman(num_factors: int) -> pd.DataFrame:
    """
    Generates a 2-level Plackett-Burman screening design.
    """
    n = num_factors
    if n < 4:
        raise ValueError("Plackett-Burman requires at least 4 factors.")
    if n > 23:
        raise ValueError("Plackett-Burman supports up to 23 factors in this module.")

    if n >= 4 and n < 8:
        generator = [1, 1, 1, -1, 1, -1, -1]
    elif n >= 8 and n < 12:
        generator = [1, 1, -1, 1, 1, 1, -1, -1, -1, 1, -1]
    elif n >= 12 and n < 16:
        generator = [1, 1, 1, 1, -1, 1, -1, 1, 1, -1, -1, 1, -1, -1, -1]
    elif n >= 16 and n < 20:
        generator = [1, 1, -1, -1, 1, 1, 1, 1, -1, 1, -1, 1, -1, -1, -1, -1, 1, 1, -1]
    elif n >= 20 and n <= 23:
        generator = [1, 1, 1, 1, 1, -1, 1, -1, 1, 1, -1, -1, 1, 1, -1, -1, 1, -1, 1, -1, -1, -1, -1]
    else:
        raise ValueError("Invalid factor count.")

    runs = len(generator)
    design = np.zeros((runs, n))
    design[:, 0] = generator

    for j in range(1, n):
        design[:, j] = np.roll(design[:, 0], j)

    design = np.vstack([design, -np.ones(n)])
    df = pd.DataFrame(design, columns=[f"Var{i + 1}" for i in range(num_factors)])
    return df


def generate_box_behnken(num_factors: int) -> pd.DataFrame:
    """
    Generates a Box-Behnken design matrix with standard center points and blocks.
    """
    n = num_factors
    # Design Skeletons
    if n == 3:
        matrix = np.array([[1, 1, 0], [1, 0, 1], [0, 1, 1]])
        blocks = [3]
        cps = [3]
    elif n == 4:
        matrix = np.array([[1, 1, 0, 0], [0, 0, 1, 1], [1, 0, 0, 1], [0, 1, 1, 0], [1, 0, 1, 0], [0, 1, 0, 1]])
        blocks = [2, 2, 2]
        cps = [1, 1, 1]
    elif n == 5:
        matrix = np.array(
            [
                [1, 1, 0, 0, 0],
                [0, 0, 1, 1, 0],
                [0, 1, 0, 0, 1],
                [1, 0, 1, 0, 0],
                [0, 0, 0, 1, 1],
                [0, 1, 1, 0, 0],
                [1, 0, 0, 1, 0],
                [0, 0, 1, 0, 1],
                [1, 0, 0, 0, 1],
                [0, 1, 0, 1, 0],
            ]
        )
        blocks = [5, 5]
        cps = [3, 3]
    elif n == 6:
        matrix = np.array(
            [
                [1, 1, 0, 1, 0, 0],
                [0, 1, 1, 0, 1, 0],
                [0, 0, 1, 1, 0, 1],
                [1, 0, 0, 1, 1, 0],
                [0, 1, 0, 0, 1, 1],
                [1, 0, 1, 0, 0, 1],
            ]
        )
        blocks = [6]
        cps = [6]
    elif n == 7:
        matrix = np.array(
            [
                [0, 0, 0, 1, 1, 1, 0],
                [1, 0, 0, 0, 0, 1, 1],
                [0, 1, 0, 0, 1, 0, 1],
                [1, 1, 0, 1, 0, 0, 0],
                [0, 0, 1, 1, 0, 0, 1],
                [1, 0, 1, 0, 1, 0, 0],
                [0, 1, 1, 0, 0, 1, 0],
            ]
        )
        blocks = [7]
        cps = [6]
    else:
        raise ValueError("Box-Behnken supports 3 to 7 factors.")

    row_ptr = 0
    out_list = []

    for i, rows_in_block in enumerate(blocks):
        block_runs = []
        for j in range(rows_in_block):
            row = matrix[row_ptr + j]
            levels_list = [[-1.0, 1.0] if v == 1 else [0.0] for v in row]
            expanded = list(itertools.product(*levels_list))
            block_runs.extend(expanded)

        # Center points
        if cps[i] > 0:
            for _ in range(cps[i]):
                block_runs.append(tuple([0.0] * n))

        # Add Block column
        block_df = pd.DataFrame(block_runs, columns=[f"Var{k + 1}" for k in range(n)])
        block_df["Block"] = i + 1
        out_list.append(block_df)

        row_ptr += rows_in_block

    df = pd.concat(out_list, ignore_index=True)
    return df


def generate_central_composite(num_factors: int, ccd_type: str) -> pd.DataFrame:
    """
    Generates CCD design matrix (Circumscribed, Inscribed, Face Centered).
    """
    n = num_factors
    # Factorial part
    factorial_combinations = list(itertools.product([-1.0, 1.0], repeat=n))
    df_fact = pd.DataFrame(factorial_combinations, columns=[f"Var{i + 1}" for i in range(n)])

    # Center points & alpha settings (matched to R defaults)
    alpha_mapping = {
        2: (1.41421356, 3, 3),
        3: (1.82574186, 4, 4),
        4: (2.19089023, 4, 4),
        5: (2.49443826, 4, 4),
        6: (2.74397734, 4, 8),
        7: (2.96984848, 4, 10),
    }

    if n in alpha_mapping:
        alpha_val, nc1, nc2 = alpha_mapping[n]
    else:
        # Fallback extrapolation
        alpha_val = (2**n) ** 0.25
        nc1, nc2 = 4, 4

    alpha = 1.0 if ccd_type == "Face Centered" else alpha_val

    # Axial (star) points
    star_runs = []
    for i in range(n):
        for val in [-alpha, alpha]:
            run = [0.0] * n
            run[i] = val
            star_runs.append(run)
    df_star = pd.DataFrame(star_runs, columns=[f"Var{i + 1}" for i in range(n)])

    # Center runs
    df_cp1 = pd.DataFrame([[0.0] * n] * nc1, columns=[f"Var{i + 1}" for i in range(n)])
    df_cp2 = pd.DataFrame([[0.0] * n] * nc2, columns=[f"Var{i + 1}" for i in range(n)])

    # Combine blocks (Block 1: Factorial + CP1, Block 2: Star + CP2)
    # R ccd drops block column eventually, but let's structure them
    df_block1 = pd.concat([df_fact, df_cp1], ignore_index=True)
    df_block2 = pd.concat([df_star, df_cp2], ignore_index=True)

    df_all = pd.concat([df_block1, df_block2], ignore_index=True)

    if ccd_type == "Inscribed":
        # Inscribed divides everything by alpha
        df_all = df_all / alpha_val

    return df_all


def federov_exchange(
    X_cand: np.ndarray,
    n_runs: int,
    fixed_indices: list[int] | None = None,
    max_iter: int = 100,
) -> list[int]:
    """
    Row-exchange algorithm to find D-optimal design.
    """
    N_cand, p = X_cand.shape

    if fixed_indices is None:
        fixed_indices = []

    n_flexible = n_runs - len(fixed_indices)

    # 1. Choose a random initial set of runs that is non-singular
    best_det = -1.0
    best_indices = []

    # Filter out fixed indices from candidate pool for flexible selection
    flexible_candidates = [i for i in range(N_cand) if i not in fixed_indices]

    for _ in range(100):
        flex_idx = list(np.random.choice(flexible_candidates, n_flexible, replace=False))
        idx = fixed_indices + flex_idx
        X = X_cand[idx, :]
        XtX = X.T @ X
        det = np.linalg.det(XtX)
        if det > best_det:
            best_det = det
            best_indices = idx

    if best_det <= 1e-10:
        # Fallback
        best_indices = fixed_indices + flexible_candidates[:n_flexible]

    indices = list(best_indices)

    for _iteration in range(max_iter):
        improved = False
        X = X_cand[indices, :]
        XtX = X.T @ X

        try:
            inv_XtX = np.linalg.inv(XtX)
        except np.linalg.LinAlgError:
            inv_XtX = np.linalg.inv(XtX + 1e-6 * np.eye(p))

        # Leverage of all candidates
        d_cand = np.sum(X_cand @ inv_XtX * X_cand, axis=1)
        d_design = d_cand[indices]

        # Leverages mapping: X_design @ inv_XtX @ X_cand.T
        X_design = X_cand[indices, :]
        d_ij = X_design @ inv_XtX @ X_cand.T

        best_swap = None
        max_delta = 1.0

        # We can only swap flexible runs (indices starting after fixed_indices)
        start_flexible_idx = len(fixed_indices)

        for i_idx in range(start_flexible_idx, n_runs):
            indices[i_idx]
            d_i = d_design[i_idx]
            for j in range(N_cand):
                if j in indices:
                    continue
                d_j = d_cand[j]
                d_val = d_ij[i_idx, j]
                delta = 1.0 + d_j - d_i + (d_i * d_j - d_val**2)
                if delta > max_delta:
                    max_delta = delta
                    best_swap = (i_idx, j)

        if best_swap is not None and max_delta > 1.0 + 1e-6:
            i_idx, j = best_swap
            indices[i_idx] = j
            improved = True

        if not improved:
            break

    return indices


def generate_d_optimal(levels: list[int], components: list[str], factor_types: list[str], nruns: int) -> pd.DataFrame:
    """
    Generates a D-Optimal design using Federov Exchange.
    """
    # 1. Build Candidate Set
    factor_names = [f"Var{i + 1}" for i in range(len(levels))]

    candidate_lists = []
    for i, fname in enumerate(factor_names):
        ft = factor_types[i]
        k = levels[i]

        # Extract factor degree from components list
        deg = 1
        for comp in components:
            if f"{fname}:{fname}:{fname}" in comp:
                deg = max(deg, 3)
            elif f"{fname}:{fname}" in comp or f"I({fname}**2)" in comp:
                deg = max(deg, 2)

        if ft == "Continuous":
            if deg == 1:
                vals = np.linspace(-1.0, 1.0, 2)
            elif deg == 2:
                vals = np.linspace(-1.0, 1.0, 3)
            else:
                vals = np.linspace(-1.0, 1.0, deg + 1)
        elif ft == "Discrete":
            vals = np.linspace(-1.0, 1.0, k)
        elif ft == "Categorical":
            # Categorical factors mapped to numeric levels in patsy formulas
            vals = np.array(range(1, k + 1), dtype=float)
        else:
            raise ValueError(f"Unknown factor type {ft}")

        candidate_lists.append(vals)

    combinations = list(itertools.product(*candidate_lists))
    df_cand = pd.DataFrame(combinations, columns=factor_names)

    # 2. Build Patsy Model Matrix for candidates
    # Normalise formula for Patsy
    patsy_terms = []
    for comp in components:
        # replace : with * or : and handle I(x**2)
        term = comp.replace(":", "*")
        patsy_terms.append(term)

    formula = "~ " + " + ".join(patsy_terms)
    X_cand = patsy.dmatrix(formula, df_cand, return_type="matrix")

    # 3. Fedorov Exchange
    best_idx = federov_exchange(np.asarray(X_cand), nruns)
    df_opt = df_cand.iloc[best_idx].copy().reset_index(drop=True)

    return df_opt


def generate_d_optimal_augment(
    existing_design: pd.DataFrame,
    levels: dict[str, int],
    components: list[str],
    factor_types: dict[str, str],
    nruns: int,
    randomize: bool = True,
) -> pd.DataFrame:
    """
    Augments an existing design with nruns additional D-optimal runs.
    """
    factor_names = list(levels.keys())
    # Scale existing design factors to [-1, 1] standard space
    scaled_existing = existing_design.copy()
    for f in factor_names:
        ft = factor_types[f]
        col = pd.to_numeric(scaled_existing[f], errors="coerce")
        if ft in ["Continuous", "Discrete"]:
            cmin = col.min()
            cmax = col.max()
            if cmin == cmax:
                scaled_existing[f] = 0.0
            else:
                scaled_existing[f] = 2.0 * (col - cmin) / (cmax - cmin) - 1.0
        else:
            # Categorical mapping
            scaled_existing[f] = col

    # Create candidate pool
    candidate_lists = []
    for f in factor_names:
        ft = factor_types[f]
        k = levels[f]
        deg = 1
        for comp in components:
            if f"{f}:{f}:{f}" in comp:
                deg = max(deg, 3)
            elif f"{f}:{f}" in comp or f"I({f}**2)" in comp:
                deg = max(deg, 2)

        if ft == "Continuous":
            vals = np.linspace(-1.0, 1.0, deg + 1)
        elif ft == "Discrete":
            vals = np.linspace(-1.0, 1.0, k)
        elif ft == "Categorical":
            vals = np.array(range(1, k + 1), dtype=float)
        candidate_lists.append(vals)

    combinations = list(itertools.product(*candidate_lists))
    df_cand = pd.DataFrame(combinations, columns=factor_names)

    # Combine existing runs + candidate set to form the full optimization pool
    # The existing runs will be fixed at indices [0 ... len(existing)-1]
    df_combined = pd.concat([scaled_existing[factor_names], df_cand], ignore_index=True)
    fixed_indices = list(range(len(scaled_existing)))

    patsy_terms = [c.replace(":", "*") for c in components]
    formula = "~ " + " + ".join(patsy_terms)
    X_combined = patsy.dmatrix(formula, df_combined, return_type="matrix")

    # Run augmentation
    all_runs_count = len(scaled_existing) + nruns
    best_idx = federov_exchange(np.asarray(X_combined), all_runs_count, fixed_indices=fixed_indices)

    df_augmented_scaled = df_combined.iloc[best_idx].copy().reset_index(drop=True)

    # Unscale factors back to native coordinate ranges
    df_final = df_augmented_scaled.copy()
    for f in factor_names:
        ft = factor_types[f]
        orig_col = pd.to_numeric(existing_design[f], errors="coerce")
        cmin = orig_col.min()
        cmax = orig_col.max()

        if ft in ["Continuous", "Discrete"]:
            scaled_col = df_final[f]
            unscaled = ((scaled_col + 1.0) / 2.0) * (cmax - cmin) + cmin
            if ft == "Discrete":
                unscaled = unscaled.apply(lambda v, oc=orig_col: oc.iloc[np.argmin(np.abs(oc - v))])
            df_final[f] = unscaled

    # Randomize new runs if requested
    if randomize:
        new_part = df_final.iloc[len(scaled_existing) :].sample(frac=1.0).reset_index(drop=True)
        df_final = pd.concat([df_final.iloc[: len(scaled_existing)], new_part], ignore_index=True)

    return df_final
