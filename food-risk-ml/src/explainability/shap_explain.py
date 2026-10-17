"""SHAP explanations of the final model's score.

SHAP attributes the model's output to its inputs. It describes how this model responds to features that
correlate with past positive samples; it does not identify causes of contamination. Contributions are in
the raw model's output units (log-odds or probability, see `units`), before any Platt calibration, which is
monotonic and so does not change their direction.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

from src.models.baselines import XGBClassifier  # noqa: E402  (None when xgboost is not installed)

try:
    import shap
except ImportError:  # ponytail: no s390x wheel; predictions still work, explanations are omitted
    shap = None


def source_feature(name: str, inputs: list[str]) -> str:
    """Map a transformed column (e.g. 'cat__product_category_x') back to its input feature."""
    base = name.split("__", 1)[-1].removeprefix("missingindicator_")
    matches = [f for f in inputs if base == f or base.startswith(f + "_")]
    return max(matches, key=len) if matches else base


class Explainer:
    def __init__(self, pipeline, background: pd.DataFrame):
        self.pre = pipeline.named_steps["preprocess"]
        model = pipeline.named_steps["model"]
        self.inputs = list(self.pre.feature_names_in_)
        self.names = list(self.pre.get_feature_names_out())
        if shap is None:
            self._exp, self.units = None, None
        elif isinstance(model, LogisticRegression):
            self._exp, self.units = shap.LinearExplainer(model, self.pre.transform(background)), "log-odds"
        elif XGBClassifier is not None and isinstance(model, XGBClassifier):
            self._exp, self.units = shap.TreeExplainer(model), "log-odds"
        elif isinstance(model, RandomForestClassifier):
            self._exp, self.units = shap.TreeExplainer(model), "probability"
        else:
            self._exp, self.units = None, None

    @property
    def supported(self) -> bool:
        return self._exp is not None

    def values(self, X: pd.DataFrame) -> np.ndarray:
        v = self._exp.shap_values(self.pre.transform(X))
        v = np.asarray(v[1] if isinstance(v, list) else v)
        return v[..., 1] if v.ndim == 3 else v

    def local(self, X: pd.DataFrame, top_k: int) -> list[list[dict]]:
        out = []
        for i, row in enumerate(self.values(X)):
            order = np.argsort(-np.abs(row))[:top_k]
            out.append([{
                "feature": self.names[j].split("__", 1)[-1],
                "source_feature": (src := source_feature(self.names[j], self.inputs)),
                "input_value": None if pd.isna(X.iloc[i][src]) else str(X.iloc[i][src]),
                "contribution": float(row[j]),
            } for j in order if row[j] != 0])
        return out

    def global_importance(self, X: pd.DataFrame) -> pd.DataFrame:
        mean_abs = np.abs(self.values(X)).mean(axis=0)
        df = pd.DataFrame({"feature": self.names, "mean_abs_shap": mean_abs})
        df["source_feature"] = [source_feature(n, self.inputs) for n in self.names]
        return df.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)


def save_global_importance(imp: pd.DataFrame, out_dir: Path, units: str) -> pd.DataFrame:
    imp.to_csv(out_dir / "shap_importance_encoded.csv", index=False)
    agg = (imp.groupby("source_feature")["mean_abs_shap"].sum().sort_values(ascending=False).reset_index())
    agg.to_csv(out_dir / "shap_importance_by_feature.csv", index=False)
    top = agg.head(20).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7, max(3, 0.35 * len(top))))
    ax.barh(top["source_feature"], top["mean_abs_shap"])
    ax.set_xlabel(f"mean |SHAP| ({units}); association with model score, not causation")
    ax.set_title("Global feature importance (test split)")
    fig.tight_layout()
    fig.savefig(out_dir / "shap_importance.png", dpi=120)
    plt.close(fig)
    return agg
