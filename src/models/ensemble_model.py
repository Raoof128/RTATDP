"""
Ensemble Model for Threat Detection
Combines Random Forest, XGBoost, and LightGBM with soft voting
"""

import numpy as np
import joblib
from typing import Tuple, Dict, Any, List, Optional
from pathlib import Path
import structlog

from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
import xgboost as xgb
import lightgbm as lgb


logger = structlog.get_logger(__name__)


class EnsembleDetector:
    """
    Ensemble threat detection model

    Combines multiple ML models using soft voting for robust predictions
    """

    def __init__(
        self,
        model_path: Optional[Path] = None,
        weights: Optional[Dict[str, float]] = None
    ):
        """
        Initialize ensemble detector

        Args:
            model_path: Path to load pre-trained models
            weights: Model weights for voting (rf, xgb, lgb)
        """
        self.weights = weights or {
            "random_forest": 0.4,
            "xgboost": 0.35,
            "lightgbm": 0.25
        }

        self.rf_model: Optional[RandomForestClassifier] = None
        self.xgb_model: Optional[xgb.XGBClassifier] = None
        self.lgb_model: Optional[lgb.LGBMClassifier] = None
        self.ensemble: Optional[VotingClassifier] = None
        self.is_trained = False

        if model_path and model_path.exists():
            self.load_models(model_path)

        logger.info("ensemble_detector_initialized", weights=self.weights)

    def build_models(
        self,
        n_jobs: int = -1,
        random_state: int = 42
    ) -> None:
        """
        Build individual models for ensemble

        Args:
            n_jobs: Number of parallel jobs
            random_state: Random seed for reproducibility
        """
        # Random Forest
        self.rf_model = RandomForestClassifier(
            n_estimators=200,
            max_depth=20,
            min_samples_split=10,
            min_samples_leaf=5,
            max_features='sqrt',
            class_weight='balanced',
            n_jobs=n_jobs,
            random_state=random_state,
            verbose=0
        )

        # XGBoost
        self.xgb_model = xgb.XGBClassifier(
            n_estimators=150,
            max_depth=10,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=10,  # For imbalanced classes
            n_jobs=n_jobs,
            random_state=random_state,
            verbosity=0
        )

        # LightGBM
        self.lgb_model = lgb.LGBMClassifier(
            n_estimators=100,
            num_leaves=31,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            is_unbalance=True,
            n_jobs=n_jobs,
            random_state=random_state,
            verbose=-1
        )

        # Create voting classifier
        self.ensemble = VotingClassifier(
            estimators=[
                ('rf', self.rf_model),
                ('xgb', self.xgb_model),
                ('lgb', self.lgb_model)
            ],
            voting='soft',  # Use probability averaging
            weights=[
                self.weights["random_forest"],
                self.weights["xgboost"],
                self.weights["lightgbm"]
            ],
            n_jobs=n_jobs
        )

        logger.info("ensemble_models_built")

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        Train ensemble model

        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features (optional)
            y_val: Validation labels (optional)

        Returns:
            dict: Training metrics
        """
        if self.ensemble is None:
            self.build_models()

        logger.info(
            "training_ensemble_started",
            train_samples=len(X_train),
            features=X_train.shape[1]
        )

        # Train ensemble
        self.ensemble.fit(X_train, y_train)
        self.is_trained = True

        # Evaluate on training set
        y_pred_train = self.ensemble.predict(X_train)
        y_proba_train = self.ensemble.predict_proba(X_train)[:, 1]

        metrics = {
            "train_accuracy": float(np.mean(y_pred_train == y_train)),
            "train_auc_roc": float(roc_auc_score(y_train, y_proba_train))
        }

        # Evaluate on validation set if provided
        if X_val is not None and y_val is not None:
            y_pred_val = self.ensemble.predict(X_val)
            y_proba_val = self.ensemble.predict_proba(X_val)[:, 1]

            metrics["val_accuracy"] = float(np.mean(y_pred_val == y_val))
            metrics["val_auc_roc"] = float(roc_auc_score(y_val, y_proba_val))

            logger.info(
                "ensemble_training_completed",
                train_accuracy=metrics["train_accuracy"],
                train_auc=metrics["train_auc_roc"],
                val_accuracy=metrics.get("val_accuracy"),
                val_auc=metrics.get("val_auc_roc")
            )
        else:
            logger.info(
                "ensemble_training_completed",
                train_accuracy=metrics["train_accuracy"],
                train_auc=metrics["train_auc_roc"]
            )

        return metrics

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict class labels

        Args:
            X: Feature array

        Returns:
            np.ndarray: Predicted labels (0 or 1)
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() or load_models() first.")

        return self.ensemble.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict class probabilities

        Args:
            X: Feature array

        Returns:
            np.ndarray: Probability of threat (shape: [n_samples, 2])
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() or load_models() first.")

        return self.ensemble.predict_proba(X)

    def predict_single(self, features: np.ndarray) -> Tuple[int, float, float]:
        """
        Predict for a single sample

        Args:
            features: Feature vector (1D array)

        Returns:
            tuple: (prediction, threat_probability, confidence)
        """
        if features.ndim == 1:
            features = features.reshape(1, -1)

        proba = self.predict_proba(features)[0]
        prediction = int(proba[1] > 0.5)
        threat_probability = float(proba[1])

        # Get individual model predictions for confidence calculation
        rf_proba = self.rf_model.predict_proba(features)[0][1]
        xgb_proba = self.xgb_model.predict_proba(features)[0][1]
        lgb_proba = self.lgb_model.predict_proba(features)[0][1]

        # Confidence is the max of individual model probabilities
        confidence = float(max(rf_proba, xgb_proba, lgb_proba))

        return prediction, threat_probability, confidence

    def evaluate(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray
    ) -> Dict[str, Any]:
        """
        Evaluate model performance

        Args:
            X_test: Test features
            y_test: Test labels

        Returns:
            dict: Evaluation metrics
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() or load_models() first.")

        y_pred = self.predict(X_test)
        y_proba = self.predict_proba(X_test)[:, 1]

        # Calculate metrics
        cm = confusion_matrix(y_test, y_pred)
        tn, fp, fn, tp = cm.ravel()

        metrics = {
            "accuracy": float(np.mean(y_pred == y_test)),
            "precision": float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0,
            "recall": float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0,
            "f1_score": 0.0,  # Will calculate below
            "auc_roc": float(roc_auc_score(y_test, y_proba)),
            "true_positives": int(tp),
            "true_negatives": int(tn),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "false_positive_rate": float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0,
            "true_positive_rate": float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        }

        # Calculate F1 score
        if metrics["precision"] + metrics["recall"] > 0:
            metrics["f1_score"] = float(
                2 * (metrics["precision"] * metrics["recall"]) /
                (metrics["precision"] + metrics["recall"])
            )

        logger.info(
            "model_evaluation_completed",
            accuracy=metrics["accuracy"],
            precision=metrics["precision"],
            recall=metrics["recall"],
            f1_score=metrics["f1_score"],
            auc_roc=metrics["auc_roc"],
            fpr=metrics["false_positive_rate"]
        )

        return metrics

    def get_feature_importance(self) -> Dict[str, np.ndarray]:
        """
        Get feature importance from individual models

        Returns:
            dict: Feature importance arrays for each model
        """
        if not self.is_trained:
            raise ValueError("Model not trained.")

        return {
            "random_forest": self.rf_model.feature_importances_,
            "xgboost": self.xgb_model.feature_importances_,
            "lightgbm": self.lgb_model.feature_importances_
        }

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

        # Save individual models
        joblib.dump(self.rf_model, save_dir / "random_forest.pkl")
        joblib.dump(self.xgb_model, save_dir / "xgboost.pkl")
        joblib.dump(self.lgb_model, save_dir / "lightgbm.pkl")

        # Save ensemble
        joblib.dump(self.ensemble, save_dir / "ensemble.pkl")

        # Save metadata
        metadata = {
            "weights": self.weights,
            "is_trained": self.is_trained
        }
        joblib.dump(metadata, save_dir / "metadata.pkl")

        logger.info("models_saved", save_dir=str(save_dir))

    def load_models(self, load_dir: Path) -> None:
        """
        Load trained models from disk

        Args:
            load_dir: Directory containing saved models
        """
        load_dir = Path(load_dir)

        if not load_dir.exists():
            raise FileNotFoundError(f"Model directory not found: {load_dir}")

        # Load individual models
        self.rf_model = joblib.load(load_dir / "random_forest.pkl")
        self.xgb_model = joblib.load(load_dir / "xgboost.pkl")
        self.lgb_model = joblib.load(load_dir / "lightgbm.pkl")

        # Load ensemble
        self.ensemble = joblib.load(load_dir / "ensemble.pkl")

        # Load metadata
        metadata = joblib.load(load_dir / "metadata.pkl")
        self.weights = metadata["weights"]
        self.is_trained = metadata["is_trained"]

        logger.info("models_loaded", load_dir=str(load_dir))


# Example usage
if __name__ == "__main__":
    from sklearn.datasets import make_classification
    from sklearn.model_selection import train_test_split

    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )

    # Generate synthetic data
    print("Generating synthetic threat detection dataset...")
    X, y = make_classification(
        n_samples=10000,
        n_features=25,  # Match our feature count
        n_informative=20,
        n_redundant=3,
        n_classes=2,
        weights=[0.95, 0.05],  # Imbalanced: 5% threats
        random_state=42
    )

    # Split data
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
    )

    print(f"Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")
    print(f"Threat rate: {np.mean(y) * 100:.2f}%")

    # Train model
    print("\nTraining ensemble model...")
    detector = EnsembleDetector()
    metrics = detector.train(X_train, y_train, X_val, y_val)

    print("\nTraining Metrics:")
    print(f"Train AUC-ROC: {metrics['train_auc_roc']:.4f}")
    print(f"Val AUC-ROC: {metrics['val_auc_roc']:.4f}")

    # Evaluate
    print("\nEvaluating on test set...")
    test_metrics = detector.evaluate(X_test, y_test)

    print("\nTest Metrics:")
    print(f"Accuracy: {test_metrics['accuracy']:.4f}")
    print(f"Precision: {test_metrics['precision']:.4f}")
    print(f"Recall: {test_metrics['recall']:.4f}")
    print(f"F1 Score: {test_metrics['f1_score']:.4f}")
    print(f"AUC-ROC: {test_metrics['auc_roc']:.4f}")
    print(f"False Positive Rate: {test_metrics['false_positive_rate']:.4f}")

    # Test single prediction
    print("\nTesting single prediction...")
    sample = X_test[0]
    pred, threat_prob, confidence = detector.predict_single(sample)

    print(f"Prediction: {'THREAT' if pred == 1 else 'BENIGN'}")
    print(f"Threat Probability: {threat_prob:.4f}")
    print(f"Confidence: {confidence:.4f}")
    print(f"Actual Label: {'THREAT' if y_test[0] == 1 else 'BENIGN'}")

    # Save models
    print("\nSaving models...")
    save_path = Path("models/ensemble")
    detector.save_models(save_path)
    print(f"Models saved to: {save_path}")
