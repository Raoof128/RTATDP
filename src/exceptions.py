"""
Custom exceptions for the threat detection system
"""


class ThreatDetectorException(Exception):
    """Base exception for threat detector"""
    pass


class DataPipelineException(ThreatDetectorException):
    """Exception in data pipeline"""
    pass


class FeatureExtractionException(ThreatDetectorException):
    """Exception during feature extraction"""
    pass


class ModelException(ThreatDetectorException):
    """Exception in ML model"""
    pass


class ModelNotTrainedException(ModelException):
    """Model has not been trained"""
    pass


class ModelLoadException(ModelException):
    """Failed to load model"""
    pass


class InferenceException(ThreatDetectorException):
    """Exception during inference"""
    pass


class IntegrationException(ThreatDetectorException):
    """Exception in SIEM/SOAR integration"""
    pass


class ConfigurationException(ThreatDetectorException):
    """Exception in configuration"""
    pass


class ValidationException(ThreatDetectorException):
    """Data validation exception"""
    pass


class RateLimitException(ThreatDetectorException):
    """Rate limit exceeded"""
    pass
