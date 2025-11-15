"""
Unit tests for Anomaly Detector
"""

import pytest
import numpy as np
from sklearn.datasets import make_classification
from pathlib import Path
import tempfile
import shutil

from src.models.anomaly_detector import AnomalyDetector


class TestAnomalyDetector:
    """Test suite for AnomalyDetector"""

    @pytest.fixture
    def sample_data(self):
        """Generate sample data (mostly normal)"""
        X_normal, _ = make_classification(
            n_samples=1000,
            n_features=25,
            n_informative=20,
            n_redundant=3,
            n_classes=2,
            weights=[0.5, 0.5],
            random_state=42
        )
        return X_normal

    @pytest.fixture
    def anomaly_data(self):
        """Generate anomalous data"""
        X_anomaly, _ = make_classification(
            n_samples=100,
            n_features=25,
            n_informative=20,
            n_redundant=3,
            n_classes=2,
            weights=[0.5, 0.5],
            random_state=123,
            shift=5.0  # Different distribution
        )
        return X_anomaly

    @pytest.fixture
    def detector(self):
        """Create detector instance"""
        return AnomalyDetector(contamination=0.02)

    def test_initialization(self, detector):
        """Test detector initialization"""
        assert detector is not None
        assert detector.contamination == 0.02
        assert not detector.is_trained

    def test_build_models(self, detector):
        """Test model building"""
        detector.build_models()

        assert detector.scaler is not None
        assert detector.isolation_forest is not None
        assert detector.one_class_svm is not None
        assert detector.lof is not None

    def test_training(self, detector, sample_data):
        """Test model training"""
        stats = detector.train(sample_data)

        assert "isolation_forest_anomalies" in stats
        assert "one_class_svm_anomalies" in stats
        assert "lof_anomalies" in stats
        assert "ensemble_anomalies" in stats
        assert detector.is_trained

    def test_prediction(self, detector, sample_data, anomaly_data):
        """Test anomaly prediction"""
        detector.train(sample_data)

        # Predict on normal data
        normal_pred = detector.predict(sample_data[:100])
        assert normal_pred.shape[0] == 100
        assert all(p in [1, -1] for p in normal_pred)

        # Predict on anomalous data
        anomaly_pred = detector.predict(anomaly_data[:20])
        assert anomaly_pred.shape[0] == 20

        # Anomalous data should have more -1 predictions
        anomaly_rate = np.mean(anomaly_pred == -1)
        normal_rate = np.mean(normal_pred == -1)
        assert anomaly_rate > normal_rate

    def test_decision_function(self, detector, sample_data):
        """Test decision function scores"""
        detector.train(sample_data)

        scores = detector.decision_function(sample_data[:10])

        assert "isolation_forest" in scores
        assert "one_class_svm" in scores
        assert "lof" in scores

        assert scores["isolation_forest"].shape[0] == 10

    def test_predict_single(self, detector, sample_data):
        """Test single sample prediction"""
        detector.train(sample_data)

        sample = sample_data[0]
        prediction, score, individual_scores = detector.predict_single(sample)

        assert prediction in [1, -1]
        assert isinstance(score, float)
        assert "isolation_forest" in individual_scores
        assert "one_class_svm" in individual_scores
        assert "lof" in individual_scores

    def test_save_load_models(self, detector, sample_data):
        """Test model saving and loading"""
        detector.train(sample_data)

        # Create temporary directory
        temp_dir = Path(tempfile.mkdtemp())

        try:
            # Save models
            detector.save_models(temp_dir)
            assert (temp_dir / "scaler.pkl").exists()
            assert (temp_dir / "isolation_forest.pkl").exists()
            assert (temp_dir / "one_class_svm.pkl").exists()
            assert (temp_dir / "local_outlier_factor.pkl").exists()

            # Load models in new detector
            new_detector = AnomalyDetector(model_path=temp_dir)
            assert new_detector.is_trained

            # Test predictions match
            sample = sample_data[0]
            pred1, score1, _ = detector.predict_single(sample)
            pred2, score2, _ = new_detector.predict_single(sample)

            assert pred1 == pred2
            assert abs(score1 - score2) < 0.1

        finally:
            # Cleanup
            shutil.rmtree(temp_dir)

    def test_untrained_prediction_error(self, detector, sample_data):
        """Test that prediction fails on untrained model"""
        with pytest.raises(ValueError, match="not trained"):
            detector.predict(sample_data[:10])

    def test_ensemble_voting(self, detector, sample_data):
        """Test ensemble voting logic"""
        detector.train(sample_data)

        # Test with custom predictions
        if_pred = np.array([1, -1, -1, 1])
        svm_pred = np.array([1, -1, 1, -1])
        lof_pred = np.array([1, -1, -1, -1])

        ensemble_pred = detector._ensemble_predict(if_pred, svm_pred, lof_pred)

        # Expected: [1, -1, -1, -1] (majority vote)
        assert ensemble_pred[0] == 1  # 3 votes for normal
        assert ensemble_pred[1] == -1  # 3 votes for anomaly
        assert ensemble_pred[2] == -1  # 2 votes for anomaly
        assert ensemble_pred[3] == -1  # 2 votes for anomaly

    def test_contamination_parameter(self):
        """Test different contamination rates"""
        detector_low = AnomalyDetector(contamination=0.01)
        detector_high = AnomalyDetector(contamination=0.05)

        assert detector_low.contamination == 0.01
        assert detector_high.contamination == 0.05


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
