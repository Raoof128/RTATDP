"""
Anomaly Detection Models
Detects zero-day attacks using unsupervised learning
"""

import numpy as np
import joblib
from typing import Tuple, Dict, Any, Optional
from pathlib import Path
import structlog

from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler


logger = structlog.get_logger(__name__)


class AnomalyDetector:
    """
    Ensemble anomaly detector using multiple unsupervised algorithms

    Detects novel/zero-day threats that don't match known patterns
    """

    def __init__(
        self,
        model_path: Optional[Path] = None,
        contamination: float = 0.02  # Expected anomaly rate (2%)
    ):
        """
        Initialize anomaly detector

        Args:
            model_path: Path to load pre-trained models
            contamination: Expected proportion of anomalies
        """
        self.contamination = contamination
        self.scaler: Optional[StandardScaler] = None
        self.isolation_forest: Optional[IsolationForest] = None
        self.one_class_svm: Optional[OneClassSVM] = None
        self.lof: Optional[LocalOutlierFactor] = None
        self.is_trained = False

        if model_path and model_path.exists():
            self.load_models(model_path)

        logger.info(
            "anomaly_detector_initialized",
            contamination=contamination
        )

    def build_models(self, random_state: int = 42) -> None:
        """
        Build anomaly detection models

        Args:
            random_state: Random seed for reproducibility
        """
        # Feature scaler
        self.scaler = StandardScaler()

        # Isolation Forest
        self.isolation_forest = IsolationForest(
            n_estimators=100,
            contamination=self.contamination,
            max_samples=256,
            random_state=random_state,
            n_jobs=-1,
            verbose=0
        )

        # One-Class SVM
        self.one_class_svm = OneClassSVM(
            kernel='rbf',
            gamma='auto',
            nu=self.contamination  # nu is similar to contamination
        )

        # Local Outlier Factor
        self.lof = LocalOutlierFactor(
            n_neighbors=20,
            contamination=self.contamination,
            novelty=True,  # Allow predict() on new data
            n_jobs=-1
        )

        logger.info("anomaly_models_built")

    def train(self, X_train: np.ndarray) -> Dict[str, Any]:
        """
        Train anomaly detection models on normal data

        Args:
            X_train: Training features (should be primarily normal traffic)

        Returns:
            dict: Training statistics
        """
        if self.isolation_forest is None:
            self.build_models()

        logger.info(
            "training_anomaly_detector_started",
            samples=len(X_train),
            features=X_train.shape[1]
        )

        # Scale features
        X_scaled = self.scaler.fit_transform(X_train)

        # Train Isolation Forest
        self.isolation_forest.fit(X_scaled)

        # Train One-Class SVM
        self.one_class_svm.fit(X_scaled)

        # Train LOF
        self.lof.fit(X_scaled)

        self.is_trained = True

        # Get predictions on training data
        if_pred = self.isolation_forest.predict(X_scaled)
        svm_pred = self.one_class_svm.predict(X_scaled)
        lof_pred = self.lof.predict(X_scaled)

        # Count anomalies detected
        stats = {
            "isolation_forest_anomalies": int(np.sum(if_pred == -1)),
            "one_class_svm_anomalies": int(np.sum(svm_pred == -1)),
            "lof_anomalies": int(np.sum(lof_pred == -1)),
            "ensemble_anomalies": 0  # Will calculate below
        }

        # Ensemble decision: Flag as anomaly if >= 2/3 models agree
        ensemble_pred = self._ensemble_predict(if_pred, svm_pred, lof_pred)
        stats["ensemble_anomalies"] = int(np.sum(ensemble_pred == -1))

        logger.info(
            "anomaly_training_completed",
            if_anomalies=stats["isolation_forest_anomalies"],
            svm_anomalies=stats["one_class_svm_anomalies"],
            lof_anomalies=stats["lof_anomalies"],
            ensemble_anomalies=stats["ensemble_anomalies"]
        )

        return stats

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict anomalies (ensemble decision)

        Args:
            X: Feature array

        Returns:
            np.ndarray: Predictions (1 = normal, -1 = anomaly)
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() or load_models() first.")

        # Scale features
        X_scaled = self.scaler.transform(X)

        # Get predictions from each model
        if_pred = self.isolation_forest.predict(X_scaled)
        svm_pred = self.one_class_svm.predict(X_scaled)
        lof_pred = self.lof.predict(X_scaled)

        # Ensemble decision
        return self._ensemble_predict(if_pred, svm_pred, lof_pred)

    def decision_function(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Get anomaly scores from each model

        Args:
            X: Feature array

        Returns:
            dict: Anomaly scores for each model
        """
        if not self.is_trained:
            raise ValueError("Model not trained.")

        X_scaled = self.scaler.transform(X)

        return {
            "isolation_forest": self.isolation_forest.decision_function(X_scaled),
            "one_class_svm": self.one_class_svm.decision_function(X_scaled),
            "lof": self.lof.decision_function(X_scaled)
        }

    def predict_single(
        self,
        features: np.ndarray
    ) -> Tuple[int, float, Dict[str, float]]:
        """
        Predict anomaly for single sample

        Args:
            features: Feature vector (1D array)

        Returns:
            tuple: (prediction, anomaly_score, individual_scores)
        """
        if features.ndim == 1:
            features = features.reshape(1, -1)

        # Get ensemble prediction
        prediction = self.predict(features)[0]

        # Get decision scores
        scores = self.decision_function(features)

        # Calculate ensemble anomaly score (average of normalized scores)
        anomaly_score = float(np.mean([
            -scores["isolation_forest"][0],  # Negative because IF returns negative scores for anomalies
            -scores["one_class_svm"][0],
            -scores["lof"][0]
        ]))

        individual_scores = {
            "isolation_forest": float(-scores["isolation_forest"][0]),
            "one_class_svm": float(-scores["one_class_svm"][0]),
            "lof": float(-scores["lof"][0])
        }

        return int(prediction), anomaly_score, individual_scores

    def _ensemble_predict(
        self,
        if_pred: np.ndarray,
        svm_pred: np.ndarray,
        lof_pred: np.ndarray
    ) -> np.ndarray:
        """
        Combine predictions from multiple models

        Args:
            if_pred: Isolation Forest predictions
            svm_pred: One-Class SVM predictions
            lof_pred: LOF predictions

        Returns:
            np.ndarray: Ensemble predictions (-1 if >= 2/3 models agree)
        """
        # Count how many models predict anomaly (-1)
        votes = (if_pred == -1).astype(int) + \
                (svm_pred == -1).astype(int) + \
                (lof_pred == -1).astype(int)

        # Predict anomaly if at least 2 out of 3 models agree
        ensemble_pred = np.where(votes >= 2, -1, 1)

        return ensemble_pred

    def save_models(self, save_dir: Path) -> None:
        """
        Save trained models to disk

        Args:
            save_dir: Directory to save models
        """
        if not self.is_trained:
            raise ValueError("No trained models to save.")

        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        # Save scaler
        joblib.dump(self.scaler, save_dir / "scaler.pkl")

        # Save models
        joblib.dump(self.isolation_forest, save_dir / "isolation_forest.pkl")
        joblib.dump(self.one_class_svm, save_dir / "one_class_svm.pkl")
        joblib.dump(self.lof, save_dir / "local_outlier_factor.pkl")

        # Save metadata
        metadata = {
            "contamination": self.contamination,
            "is_trained": self.is_trained
        }
        joblib.dump(metadata, save_dir / "metadata.pkl")

        logger.info("anomaly_models_saved", save_dir=str(save_dir))

    def load_models(self, load_dir: Path) -> None:
        """
        Load trained models from disk

        Args:
            load_dir: Directory containing saved models
        """
        load_dir = Path(load_dir)

        if not load_dir.exists():
            raise FileNotFoundError(f"Model directory not found: {load_dir}")

        # Load scaler
        self.scaler = joblib.load(load_dir / "scaler.pkl")

        # Load models
        self.isolation_forest = joblib.load(load_dir / "isolation_forest.pkl")
        self.one_class_svm = joblib.load(load_dir / "one_class_svm.pkl")
        self.lof = joblib.load(load_dir / "local_outlier_factor.pkl")

        # Load metadata
        metadata = joblib.load(load_dir / "metadata.pkl")
        self.contamination = metadata["contamination"]
        self.is_trained = metadata["is_trained"]

        logger.info("anomaly_models_loaded", load_dir=str(load_dir))


# Example usage
if __name__ == "__main__":
    from sklearn.datasets import make_classification

    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )

    # Generate normal data
    print("Generating synthetic normal traffic...")
    X_normal, _ = make_classification(
        n_samples=9000,
        n_features=25,
        n_informative=20,
        n_redundant=3,
        n_classes=2,
        weights=[0.5, 0.5],
        random_state=42
    )

    # Generate anomalies (different distribution)
    print("Generating synthetic anomalies...")
    X_anomaly, _ = make_classification(
        n_samples=200,
        n_features=25,
        n_informative=20,
        n_redundant=3,
        n_classes=2,
        weights=[0.5, 0.5],
        random_state=123,  # Different seed
        shift=5.0  # Shift distribution
    )

    # Combine for testing
    X_test = np.vstack([X_normal[:100], X_anomaly[:20]])
    y_test = np.array([1] * 100 + [-1] * 20)  # 1 = normal, -1 = anomaly

    # Train on normal data only
    print("\nTraining anomaly detector on normal data...")
    detector = AnomalyDetector(contamination=0.02)
    stats = detector.train(X_normal[100:])  # Use different samples for training

    print("\nTraining Statistics:")
    print(f"IF anomalies detected: {stats['isolation_forest_anomalies']}")
    print(f"SVM anomalies detected: {stats['one_class_svm_anomalies']}")
    print(f"LOF anomalies detected: {stats['lof_anomalies']}")
    print(f"Ensemble anomalies detected: {stats['ensemble_anomalies']}")

    # Test on mixed data
    print("\nTesting on mixed data (100 normal + 20 anomalies)...")
    predictions = detector.predict(X_test)

    # Calculate detection metrics
    true_anomalies = np.sum(y_test == -1)
    predicted_anomalies = np.sum(predictions == -1)
    correct_anomalies = np.sum((predictions == -1) & (y_test == -1))

    print(f"\nTrue anomalies: {true_anomalies}")
    print(f"Predicted anomalies: {predicted_anomalies}")
    print(f"Correctly detected: {correct_anomalies}")
    print(f"Detection rate: {correct_anomalies / true_anomalies * 100:.2f}%")

    # Test single prediction
    print("\nTesting single anomaly prediction...")
    sample_anomaly = X_anomaly[0]
    pred, score, individual_scores = detector.predict_single(sample_anomaly)

    print(f"Prediction: {'ANOMALY' if pred == -1 else 'NORMAL'}")
    print(f"Anomaly Score: {score:.4f}")
    print(f"Individual Scores: {individual_scores}")

    # Save models
    print("\nSaving models...")
    save_path = Path("models/anomaly")
    detector.save_models(save_path)
    print(f"Models saved to: {save_path}")
