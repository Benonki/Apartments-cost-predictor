import numpy as np
import pandas as pd


STATISTIC_COLUMNS = (
    "count", "min", "max", "mean", "std", "median", "q1", "q3", "p10", "p90",
)


def descriptive_statistics(frame, columns=None):
    if columns is None:
        columns = list(frame.select_dtypes(include="number").columns)
    results = []
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        values = values.replace([np.inf, -np.inf], np.nan).dropna()
        quantiles = values.quantile([0.1, 0.25, 0.5, 0.75, 0.9])
        results.append({
            "count": int(values.count()),
            "min": values.min(), "max": values.max(), "mean": values.mean(),
            "std": values.std(ddof=1), "median": quantiles.loc[0.5],
            "q1": quantiles.loc[0.25], "q3": quantiles.loc[0.75],
            "p10": quantiles.loc[0.1], "p90": quantiles.loc[0.9],
        })
    result = pd.DataFrame(results, index=list(columns), columns=STATISTIC_COLUMNS)
    result.index.name = "variable"
    return result


def finite_pairs(x_values, y_values):
    x = pd.to_numeric(pd.Series(x_values), errors="coerce").to_numpy(
        dtype=float, na_value=np.nan,
    )
    y = pd.to_numeric(pd.Series(y_values), errors="coerce").to_numpy(
        dtype=float, na_value=np.nan,
    )
    if x.ndim != 1 or y.ndim != 1 or len(x) != len(y):
        raise ValueError("Zmienne muszą mieć taką samą liczbę obserwacji.")
    mask = np.isfinite(x) & np.isfinite(y)
    return x[mask], y[mask]


def pearson_correlation(x_values, y_values):
    x, y = finite_pairs(x_values, y_values)
    if len(x) < 2:
        raise ValueError("Korelacja wymaga co najmniej dwóch poprawnych par wartości.")
    dx, dy = x - x.mean(), y - y.mean()
    norm_x, norm_y = np.linalg.norm(dx), np.linalg.norm(dy)
    if norm_x == 0 or norm_y == 0:
        return float("nan")
    return float(np.clip(np.dot(dx / norm_x, dy / norm_y), -1.0, 1.0))


def linear_regression(x_values, y_values):
    x, y = finite_pairs(x_values, y_values)
    if len(x) < 2:
        raise ValueError("Regresja wymaga co najmniej dwóch poprawnych par wartości.")
    dx, dy = x - x.mean(), y - y.mean()
    denominator = float(np.dot(dx, dx))
    if denominator == 0:
        raise ValueError("Regresja jest nieokreślona: zmienna X ma stałą wartość.")
    slope = float(np.dot(dx, dy) / denominator)
    intercept = float(y.mean() - slope * x.mean())
    residuals = y - (slope * x + intercept)
    residual_sum = float(np.dot(residuals, residuals))
    total_sum = float(np.dot(dy, dy))
    return {
        "n": len(x), "slope": slope, "intercept": intercept,
        "r": pearson_correlation(x, y),
        "r_squared": float(np.clip(1 - residual_sum / total_sum, 0, 1))
        if total_sum else float("nan"),
        "rmse": float(np.sqrt(residual_sum / len(x))),
        "x_min": float(x.min()), "x_max": float(x.max()),
    }
