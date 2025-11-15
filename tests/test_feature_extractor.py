"""
Unit tests for Feature Extractor
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
import numpy as np

from src.feature_engineering.feature_extractor import FeatureExtractor, FeatureVector
from src.data_pipeline.schemas import NetworkEvent, Protocol


class TestFeatureVector:
    """Test suite for FeatureVector"""

    def test_feature_vector_creation(self):
        """Test creating a feature vector"""
        fv = FeatureVector(
            source_ip="192.168.1.100",
            timestamp=datetime.utcnow(),
            event_id="test-123",
            conn_count_1min=10,
            unique_dst_ports_1min=5,
            payload_entropy=6.5
        )

        assert fv.source_ip == "192.168.1.100"
        assert fv.conn_count_1min == 10
        assert fv.unique_dst_ports_1min == 5
        assert fv.payload_entropy == 6.5

    def test_to_numpy_array(self):
        """Test conversion to numpy array"""
        fv = FeatureVector(
            source_ip="192.168.1.100",
            timestamp=datetime.utcnow(),
            event_id="test-123",
            conn_count_1min=10,
            unique_dst_ports_1min=5
        )

        array = fv.to_numpy_array()

        assert isinstance(array, np.ndarray)
        assert array.dtype == np.float32
        assert len(array) == fv.feature_count

    def test_feature_count(self):
        """Test feature count property"""
        fv = FeatureVector(
            source_ip="192.168.1.100",
            timestamp=datetime.utcnow(),
            event_id="test-123"
        )

        # Should have 25 features (matching our design)
        assert fv.feature_count == 25


class TestFeatureExtractor:
    """Test suite for FeatureExtractor"""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client"""
        mock = Mock()
        mock.ping.return_value = True
        mock.zcount.return_value = 10
        mock.scard.return_value = 5
        mock.sismember.return_value = False
        mock.exists.return_value = False
        mock.get.return_value = None
        return mock

    @pytest.fixture
    def extractor(self, mock_redis):
        """Create extractor with mock Redis"""
        extractor = FeatureExtractor()
        extractor.redis = mock_redis
        return extractor

    @pytest.fixture
    def sample_event(self):
        """Create a sample network event"""
        return NetworkEvent(
            event_id="net-123",
            source_system="zeek",
            source_ip="192.168.1.100",
            destination_ip="8.8.8.8",
            source_port=54321,
            destination_port=53,
            protocol=Protocol.DNS,
            bytes_sent=512,
            bytes_received=1024,
            dns_query="example.com",
            payload="test payload data"
        )

    def test_initialization(self, mock_redis):
        """Test extractor initialization"""
        extractor = FeatureExtractor(redis_client=mock_redis)
        assert extractor.redis is not None

    def test_extract_from_network_event(self, extractor, sample_event):
        """Test feature extraction from network event"""
        features = extractor.extract_from_network_event(sample_event)

        assert isinstance(features, FeatureVector)
        assert features.source_ip == "192.168.1.100"
        assert features.event_id == "net-123"
        assert features.is_dns  # Should detect DNS protocol
        assert not features.is_http

    def test_calculate_entropy(self, extractor):
        """Test entropy calculation"""
        # Uniform data (high entropy)
        uniform_entropy = extractor._calculate_entropy("abcdefghijklmnop")
        assert uniform_entropy > 3.0

        # Repetitive data (low entropy)
        repetitive_entropy = extractor._calculate_entropy("aaaaaaaaaaaaaaaa")
        assert repetitive_entropy < 1.0

        # Empty string
        empty_entropy = extractor._calculate_entropy("")
        assert empty_entropy == 0.0

    def test_behavioral_features(self, extractor, sample_event, mock_redis):
        """Test behavioral feature extraction"""
        # Mock novel port detection
        mock_redis.sismember.return_value = False  # Port not seen before

        features = extractor.extract_from_network_event(sample_event)

        assert features.is_novel_port  # Should be detected as novel

    def test_off_hours_detection(self, extractor, sample_event):
        """Test off-hours activity detection"""
        # Test during business hours (10 AM)
        with patch('src.feature_engineering.feature_extractor.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(2025, 11, 15, 10, 0, 0)
            sample_event.timestamp = datetime(2025, 11, 15, 10, 0, 0)

            features = extractor.extract_from_network_event(sample_event)
            assert not features.off_hours_activity

        # Test off-hours (2 AM)
        with patch('src.feature_engineering.feature_extractor.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(2025, 11, 15, 2, 0, 0)
            sample_event.timestamp = datetime(2025, 11, 15, 2, 0, 0)

            features = extractor.extract_from_network_event(sample_event)
            assert features.off_hours_activity

    def test_protocol_specific_features(self, extractor, sample_event):
        """Test protocol-specific feature detection"""
        # DNS event
        sample_event.protocol = Protocol.DNS
        features = extractor.extract_from_network_event(sample_event)
        assert features.is_dns
        assert not features.is_http
        assert not features.is_ssh

        # HTTP event
        sample_event.protocol = Protocol.HTTP
        features = extractor.extract_from_network_event(sample_event)
        assert features.is_http
        assert not features.is_dns

    def test_dns_entropy_calculation(self, extractor, sample_event):
        """Test DNS query entropy calculation"""
        sample_event.dns_query = "malicious-random-string-12345.com"
        features = extractor.extract_from_network_event(sample_event)

        assert features.dns_entropy > 0.0

    def test_store_event_data(self, extractor, sample_event, mock_redis):
        """Test event data storage in Redis"""
        extractor._store_event_data(sample_event)

        # Verify Redis calls were made
        assert mock_redis.zadd.called
        assert mock_redis.sadd.called
        assert mock_redis.expire.called

    def test_feature_array_shape(self, extractor, sample_event):
        """Test that feature array has correct shape"""
        features = extractor.extract_from_network_event(sample_event)
        array = features.to_numpy_array()

        # Should have 25 features
        assert array.shape == (25,)
        assert array.dtype == np.float32


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
