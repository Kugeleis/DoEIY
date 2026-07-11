import numpy as np
import pandas as pd
import pytest

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


def test_full_factorial() -> None:
    df = generate_full_factorial([2, 3])
    assert isinstance(df, pd.DataFrame)
    assert df.shape == (6, 2)
    assert list(df.columns) == ["Var1", "Var2"]


def test_latin_hypercube() -> None:
    df = generate_latin_hypercube(num_factors=3, num_runs=10)
    assert isinstance(df, pd.DataFrame)
    assert df.shape == (10, 3)
    assert np.all(df >= -1.0) and np.all(df <= 1.0)


def test_plackett_burman() -> None:
    # 4 factors -> 7 runs + 1 row of -1s = 8 runs
    df = generate_plackett_burman(4)
    assert isinstance(df, pd.DataFrame)
    assert df.shape == (8, 4)

    # 12 factors -> 15 runs + 1 = 16 runs
    df2 = generate_plackett_burman(12)
    assert df2.shape == (16, 12)

    with pytest.raises(ValueError):
        generate_plackett_burman(3)
    with pytest.raises(ValueError):
        generate_plackett_burman(24)


def test_box_behnken() -> None:
    # 3 factors -> 12 factorial points + 3 center points = 15 runs
    df = generate_box_behnken(3)
    assert isinstance(df, pd.DataFrame)
    assert "Block" in df.columns
    assert df.shape == (15, 4)

    # 4 factors -> 24 factorial points + 3 center points = 27 runs
    df2 = generate_box_behnken(4)
    assert df2.shape == (27, 5)

    with pytest.raises(ValueError):
        generate_box_behnken(2)
    with pytest.raises(ValueError):
        generate_box_behnken(8)


def test_central_composite() -> None:
    # 3 factors: 8 runs + 4 CP in Block 1, 6 star + 4 CP in Block 2 = 22 runs
    df = generate_central_composite(3, "Circumscribed")
    assert isinstance(df, pd.DataFrame)
    assert df.shape == (22, 3)

    # Face Centered: all elements within [-1, 1]
    df_fc = generate_central_composite(3, "Face Centered")
    assert df_fc.shape == (22, 3)
    assert np.all(df_fc >= -1.0) and np.all(df_fc <= 1.0)


def test_fractional_factorial() -> None:
    res = generate_fractional_factorial(8, 4, 1)
    assert isinstance(res, dict)
    assert "Design" in res
    assert "Resolution" in res

    df = res["Design"]
    assert df.shape == (8, 4)
    assert "Resolution" in res["Resolution"]


def test_d_optimal() -> None:
    levels = [3, 3]
    components = ["Var1", "Var2", "I(Var1**2)", "I(Var2**2)", "Var1:Var2"]
    factor_types = ["Continuous", "Continuous"]
    df = generate_d_optimal(levels, components, factor_types, nruns=6)
    assert isinstance(df, pd.DataFrame)
    assert df.shape == (6, 2)


def test_d_optimal_augment() -> None:
    existing = pd.DataFrame({"Var1": [1.0, -1.0, 1.0], "Var2": [1.0, 1.0, -1.0]})
    levels = {"Var1": 3, "Var2": 3}
    components = ["Var1", "Var2", "I(Var1**2)", "I(Var2**2)", "Var1:Var2"]
    factor_types = {"Var1": "Continuous", "Var2": "Continuous"}
    df = generate_d_optimal_augment(existing, levels, components, factor_types, nruns=3, randomize=False)
    assert isinstance(df, pd.DataFrame)
    assert df.shape == (6, 2)
    # Check that existing runs are preserved
    assert np.allclose(df.iloc[:3]["Var1"], existing["Var1"])
    assert np.allclose(df.iloc[:3]["Var2"], existing["Var2"])
