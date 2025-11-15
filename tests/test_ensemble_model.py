"""
Unit tests for Ensemble Model
"""

import pytest
import numpy as np
from sklearn.datasets import make_classification
from pathlib import Path
import tempfile
import shutil

from src.models.ensemble_model import EnsembleDetector


class TestEnsembleDetector:
    """Test suite for EnsembleDetector"""

    @pytest.fixture
    def sample_data(self):
        """Generate sample training data"""
        X, y = make_classification(
            n_samples=1000,
            n_features=25,
            n_informative=20,
            n_redundant=3,
            n_classes=2,
            weights=[0.9, 0.1],
            random_state=42
        )
        return X, y

    @pytest.fixture
    def detector(self):
        """Create detector instance"""
        return EnsembleDetector()

    def test_initialization(self, detector):
        """Test detector initialization"""
        assert detector is not None
        assert detector.weights is not None
        assert "random_forest" in detector.weights
        assert "xgboost" in detector.weights
        assert "lightgbm" in detector.weights

    def test_build_models(self, detector):
        """Test model building"""
        detector.build_models()

        assert detector.rf_model is not None
        assert detector.xgb_model is not None
        assert detector.lgb_model is not None
        assert detector.ensemble is not None

    def test_training(self, detector, sample_data):
        """Test model training"""
        X, y = sample_data
        X_train, X_val = X[:800], X[800:]
        y_train, y_val = y[:800], y[800:]

        metrics = detector.train(X_train, y_train, X_val, y_val)

        assert "train_accuracy" in metrics
        assert "train_auc_roc" in metrics
        assert "val_accuracy" in metrics
        assert "val_auc_roc" in metrics
        assert detector.is_trained

    def test_prediction(self, detector, sample_data):
        """Test prediction"""
        X, y = sample_data
        X_train, X_test = X[:800], X[800:]
        y_train, y_test = y[:800], y[800:]

        detector.train(X_train, y_train)
        predictions = detector.predict(X_test)

        assert predictions.shape[0] == X_test.shape[0]
        assert all(p in [0, 1] for p in predictions)

    def test_predict_proba(self, detector, sample_data):
        """Test probability prediction"""
        X, y = sample_data
        detector.train(X[:800], y[:800])

        probabilities = detector.predict_proba(X[800:])

        assert probabilities.shape == (200, 2)
        assert all(0 <= p <= 1 for p in probabilities.flatten())

    def test_predict_single(self, detector, sample_data):
        """Test single sample prediction"""
        X, y = sample_data
        detector.train(X[:800], y[:800])

        sample = X[800]
        prediction, threat_prob, confidence = detector.predict_single(sample)

        assert prediction in [0, 1]
        assert 0 <= threat_prob <= 1
        assert 0 <= confidence <= 1

    def test_evaluate(self, detector, sample_data):
        """Test model evaluation"""
        X, y = sample_data
        X_train, X_test = X[:800], X[800:]
        y_train, y_test = y[:800], y[800:]

        detector.train(X_train, y_train)
        metrics = detector.evaluate(X_test, y_test)

        assert "accuracy" in metrics
        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1_score" in metrics
        assert "auc_roc" in metrics
        assert "false_positive_rate" in metrics

    def test_save_load_models(self, detector, sample_data):
        """Test model saving and loading"""
        X, y = sample_data
        detector.train(X[:800], y[:800])

        # Create temporary directory
        temp_dir = Path(tempfile.mkdtemp())

        try:
            # Save models
            detector.save_models(temp_dir)
            assert (temp_dir / "random_forest.pkl").exists()
            assert (temp_dir / "xgboost.pkl").exists()
            assert (temp_dir / "lightgbm.pkl").exists()
            assert (temp_dir / "ensemble.pkl").exists()

            # Load models in new detector
            new_detector = EnsembleDetector(model_path=temp_dir)
            assert new_detector.is_trained

            # Test predictions match
            sample = X[800]
            pred1, prob1, conf1 = detector.predict_single(sample)
            pred2, prob2, conf2 = new_detector.predict_single(sample)

            assert pred1 == pred2
            assert abs(prob1 - prob2) < 0.001

        finally:
            # Cleanup
            shutil.rmtree(temp_dir)

    def test_feature_importance(self, detector, sample_data):
        """Test feature importance extraction"""
        X, y = sample_data
        detector.train(X[:800], y[:800])

        importance = detector.get_feature_importance()

        assert "random_forest" in importance
        assert "xgboost" in importance
        assert "lightgbm" in importance

        assert importance["random_forest"].shape[0] == X.shape[1]

    def test_untrained_prediction_error(self, detector, sample_data):
        """Test that prediction fails on untrained model"""
        X, _ = sample_data

        with pytest.raises(ValueError, match="not trained"):
            detector.predict(X[:10])

    def test_weights_sum(self, detector):
        """Test that ensemble weights sum correctly"""
        total_weight = sum(detector.weights.values())
        assert abs(total_weight - 1.0) < 0.01  # Should sum to 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
