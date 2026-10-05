from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import IsolationForest


@dataclass
class AnomalyResult:
    anomaly_score: float
    is_anomaly: bool


class EngineAnomalyDetector:
    """
    Unsupervised anomaly detector for AeroTwin.

    The model learns the statistical pattern of normal
    synthetic engine operation.

    This is a development ML model and is NOT validated
    against real aircraft-engine failure data.
    """

    def __init__(
        self,
        contamination: float = 0.05,
        random_state: int = 42,
    ):
        self.model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
            n_estimators=200,
        )

        self.is_fitted = False
        self.training_samples = 0

    def fit(
        self,
        normal_data: list[list[float]],
    ) -> None:

        data = np.asarray(
            normal_data,
            dtype=float,
        )

        if data.ndim != 2:
            raise ValueError(
                "Training data must be a 2D array."
            )

        if len(data) < 20:
            raise ValueError(
                "At least 20 normal samples are required."
            )

        if not np.isfinite(data).all():
            raise ValueError(
                "Training data contains NaN or infinite values."
            )

        self.model.fit(data)

        self.is_fitted = True
        self.training_samples = len(data)

    def predict(
        self,
        sample: list[float],
    ) -> AnomalyResult:

        if not self.is_fitted:
            raise RuntimeError(
                "The anomaly detector must be fitted "
                "before prediction."
            )

        data = np.asarray(
            sample,
            dtype=float,
        ).reshape(1, -1)

        if not np.isfinite(data).all():
            raise ValueError(
                "Prediction sample contains "
                "NaN or infinite values."
            )

        prediction = self.model.predict(data)[0]

        raw_score = self.model.decision_function(data)[0]

        # Convert the Isolation Forest decision score
        # into a convenient 0-1 anomaly scale.
        anomaly_score = float(
            np.clip(
                0.5 - raw_score,
                0.0,
                1.0,
            )
        )

        return AnomalyResult(
            anomaly_score=anomaly_score,
            is_anomaly=(
                prediction == -1
            ),
        )