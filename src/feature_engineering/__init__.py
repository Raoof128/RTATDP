"""
Feature Engineering Module
Transforms raw security events into ML-ready features
"""

from .feature_extractor import FeatureExtractor, FeatureVector
from .temporal_aggregator import TemporalAggregator
from .statistical_features import StatisticalFeatureCalculator

__all__ = [
    "FeatureExtractor",
    "FeatureVector",
    "TemporalAggregator",
    "StatisticalFeatureCalculator",
]
