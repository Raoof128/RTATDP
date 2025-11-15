# Contributing to AI Threat Detection Pipeline

Thank you for considering contributing to this project! This document provides guidelines for contributing.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help create a positive environment for all contributors

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in Issues
2. Use the bug report template
3. Include:
   - Clear description of the issue
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, etc.)
   - Relevant logs or error messages

### Suggesting Enhancements

1. Check if the enhancement has been suggested
2. Provide clear use case and benefits
3. Consider implementation complexity
4. Discuss in Issues before implementing large features

### Pull Requests

1. **Fork the repository**

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation as needed

4. **Run tests**
   ```bash
   # Run linting
   black src/ tests/
   flake8 src/ tests/

   # Run tests
   pytest tests/ -v --cov=src
   ```

5. **Commit your changes**
   - Use clear, descriptive commit messages
   - Follow conventional commits format:
     ```
     feat: add anomaly detection for DNS queries
     fix: correct feature scaling in preprocessing
     docs: update API documentation
     test: add unit tests for ensemble model
     ```

6. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Open a Pull Request**
   - Provide clear description of changes
   - Reference related issues
   - Ensure CI/CD checks pass

## Development Setup

```bash
# Clone repository
git clone https://github.com/your-org/ai-threat-detector.git
cd ai-threat-detector

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-cov black flake8 mypy

# Run tests
pytest tests/ -v
```

## Code Style

- **Python**: Follow PEP 8
- **Line length**: Maximum 120 characters
- **Docstrings**: Use Google-style docstrings
- **Type hints**: Use type hints for function signatures
- **Formatting**: Use Black for code formatting

### Example

```python
def extract_features(
    event: NetworkEvent,
    window_size: int = 60
) -> FeatureVector:
    """
    Extract features from network event.

    Args:
        event: Network event to process
        window_size: Time window in seconds for aggregations

    Returns:
        FeatureVector containing extracted features

    Raises:
        ValueError: If event is invalid
    """
    # Implementation
    pass
```

## Testing Guidelines

- **Unit tests**: Test individual functions and classes
- **Integration tests**: Test component interactions
- **Test coverage**: Aim for >85% coverage
- **Test naming**: `test_<function_name>_<scenario>`

```python
def test_ensemble_predict_returns_valid_probability():
    """Test that ensemble model returns probability in [0, 1]"""
    # Arrange
    detector = EnsembleDetector()
    X_train, y_train = generate_sample_data()
    detector.train(X_train, y_train)

    # Act
    X_test = generate_sample_data()[0][:10]
    probabilities = detector.predict_proba(X_test)

    # Assert
    assert all(0 <= p <= 1 for p in probabilities.flatten())
```

## Documentation

- Update README.md for user-facing changes
- Update architecture docs for design changes
- Add docstrings to all public functions/classes
- Include examples in docstrings when helpful

## Adding New Detection Rules

1. Create rule in appropriate format (Sigma/YARA)
2. Add to `configs/rules/`
3. Document rule purpose and false positive considerations
4. Add test cases

## Adding New ML Features

1. Document feature rationale
2. Implement in `feature_engineering/`
3. Add feature to `FeatureVector` schema
4. Update model training pipeline
5. Evaluate impact on model performance

## Release Process

1. Update version in `setup.py`
2. Update CHANGELOG.md
3. Create release tag
4. Build and test Docker image
5. Deploy to staging for validation
6. Production deployment after approval

## Questions?

- Open an issue for discussion
- Check existing documentation
- Review past issues and PRs

Thank you for contributing! 🚀
