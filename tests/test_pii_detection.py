# Copyright 2026 CVS Health and/or one of its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This file uses the following unmodified third-party packages,
# each retaining its original copyright and license:
#   pytest (MIT)

"""
Tests for PII/PHI detection functionality using Microsoft Presidio.
"""

import pytest
from unittest.mock import Mock, patch
from askrita.config_manager import PIIDetectionConfig
from askrita.utils.pii_detector import PIIDetector, PIIDetectionResult, create_pii_detector, PRESIDIO_AVAILABLE
from askrita.exceptions import ConfigurationError


class TestPIIDetectionConfig:
    """Test PII detection configuration."""

    def test_default_config(self):
        """Test default PII detection configuration."""
        config = PIIDetectionConfig()

        assert config.enabled is False  # Disabled by default
        assert config.block_on_detection is True
        assert config.log_pii_attempts is True
        assert config.language == "en"
        assert config.confidence_threshold == 0.5
        assert config.validate_sample_data is True
        assert config.sample_data_rows == 100
        assert config.redact_in_logs is True
        assert "PERSON" in config.entities
        assert "EMAIL_ADDRESS" in config.entities
        assert "CREDIT_CARD" in config.entities

    def test_custom_config(self):
        """Test custom PII detection configuration."""
        config = PIIDetectionConfig(
            enabled=True,
            block_on_detection=False,
            confidence_threshold=0.8,
            entities=["PERSON", "EMAIL_ADDRESS"],
            sample_data_rows=50
        )

        assert config.enabled is True
        assert config.block_on_detection is False
        assert config.confidence_threshold == 0.8
        assert len(config.entities) == 2
        assert config.sample_data_rows == 50


@pytest.mark.skipif(not PRESIDIO_AVAILABLE, reason="Presidio analyzer not available")
class TestPIIDetector:
    """Test PII detector functionality when Presidio is available."""

    @pytest.fixture
    def pii_config(self):
        """Create test PII configuration."""
        return PIIDetectionConfig(
            enabled=True,
            block_on_detection=True,
            confidence_threshold=0.5,
            entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"],
            validate_sample_data=False  # Skip sample data validation in tests
        )

    @patch('askrita.utils.pii_detector.AnalyzerEngine')
    @patch('askrita.utils.pii_detector.NlpEngineProvider')
    def test_pii_detector_initialization(self, mock_nlp_provider, mock_analyzer, pii_config):
        """Test PII detector initialization."""
        # Mock the NLP engine provider and analyzer
        mock_provider_instance = Mock()
        mock_nlp_engine = Mock()
        mock_provider_instance.create_engine.return_value = mock_nlp_engine
        mock_nlp_provider.return_value = mock_provider_instance

        mock_analyzer_instance = Mock()
        mock_analyzer.return_value = mock_analyzer_instance

        # Create detector
        detector = PIIDetector(pii_config)

        # Verify initialization
        assert detector.config == pii_config
        assert detector.analyzer == mock_analyzer_instance
        mock_nlp_provider.assert_called_once()
        mock_analyzer.assert_called_once()

    def test_pii_detector_invalid_config(self):
        """Test PII detector with invalid configuration."""
        # Empty entities list
        config = PIIDetectionConfig(enabled=True, entities=[])
        with pytest.raises(ConfigurationError, match="entities list cannot be empty"):
            PIIDetector(config)

        # Invalid confidence threshold
        config = PIIDetectionConfig(enabled=True, confidence_threshold=1.5)
        with pytest.raises(ConfigurationError, match="confidence threshold must be between"):
            PIIDetector(config)

        # Invalid sample data rows
        config = PIIDetectionConfig(enabled=True, sample_data_rows=0)
        with pytest.raises(ConfigurationError, match="Sample data rows must be at least 1"):
            PIIDetector(config)

    @patch('askrita.utils.pii_detector.AnalyzerEngine')
    @patch('askrita.utils.pii_detector.NlpEngineProvider')
    def test_detect_pii_no_pii_found(self, mock_nlp_provider, mock_analyzer, pii_config):
        """Test PII detection when no PII is found."""
        # Setup mocks
        mock_provider_instance = Mock()
        mock_nlp_engine = Mock()
        mock_provider_instance.create_engine.return_value = mock_nlp_engine
        mock_nlp_provider.return_value = mock_provider_instance

        mock_analyzer_instance = Mock()
        mock_analyzer_instance.analyze.return_value = []  # No PII found
        mock_analyzer.return_value = mock_analyzer_instance

        # Create detector and test
        detector = PIIDetector(pii_config)
        result = detector.detect_pii_in_text("What are the total sales for this month?")

        # Verify results
        assert isinstance(result, PIIDetectionResult)
        assert result.has_pii is False
        assert result.blocked is False
        assert len(result.detected_entities) == 0
        assert len(result.confidence_scores) == 0
        assert result.analysis_time_ms > 0

    @patch('askrita.utils.pii_detector.AnalyzerEngine')
    @patch('askrita.utils.pii_detector.NlpEngineProvider')
    def test_detect_pii_with_pii_found(self, mock_nlp_provider, mock_analyzer, pii_config):
        """Test PII detection when PII is found."""
        # Setup mocks
        mock_provider_instance = Mock()
        mock_nlp_engine = Mock()
        mock_provider_instance.create_engine.return_value = mock_nlp_engine
        mock_nlp_provider.return_value = mock_provider_instance

        # Mock PII detection result
        mock_pii_result = Mock()
        mock_pii_result.entity_type = "PERSON"
        mock_pii_result.start = 0
        mock_pii_result.end = 10
        mock_pii_result.score = 0.9

        mock_analyzer_instance = Mock()
        mock_analyzer_instance.analyze.return_value = [mock_pii_result]
        mock_analyzer.return_value = mock_analyzer_instance

        # Create detector and test
        detector = PIIDetector(pii_config)
        result = detector.detect_pii_in_text("John Smith called about his account")

        # Verify results
        assert result.has_pii is True
        assert result.blocked is True  # Should be blocked with default config
        assert len(result.detected_entities) == 1
        assert result.detected_entities[0]["entity_type"] == "PERSON"
        assert result.detected_entities[0]["score"] == 0.9
        assert result.max_confidence == 0.9
        assert "PERSON" in result.entity_types

    @patch('askrita.utils.pii_detector.AnalyzerEngine')
    @patch('askrita.utils.pii_detector.NlpEngineProvider')
    def test_detect_pii_low_confidence(self, mock_nlp_provider, mock_analyzer, pii_config):
        """Test PII detection with low confidence scores."""
        # Setup mocks
        mock_provider_instance = Mock()
        mock_nlp_engine = Mock()
        mock_provider_instance.create_engine.return_value = mock_nlp_engine
        mock_nlp_provider.return_value = mock_provider_instance

        # Mock low confidence PII result
        mock_pii_result = Mock()
        mock_pii_result.entity_type = "PERSON"
        mock_pii_result.start = 0
        mock_pii_result.end = 4
        mock_pii_result.score = 0.3  # Below threshold

        mock_analyzer_instance = Mock()
        mock_analyzer_instance.analyze.return_value = [mock_pii_result]
        mock_analyzer.return_value = mock_analyzer_instance

        # Create detector and test
        detector = PIIDetector(pii_config)
        result = detector.detect_pii_in_text("John mentioned the report")

        # Verify results - should not detect PII due to low confidence
        assert result.has_pii is False
        assert result.blocked is False
        assert len(result.detected_entities) == 0


class TestPIIDetectorWithoutPresidio:
    """Test PII detector behavior when Presidio is not available."""

    def test_create_pii_detector_presidio_unavailable(self):
        """Test creating PII detector when Presidio is not available."""
        config = PIIDetectionConfig(enabled=True)

        with patch('askrita.utils.pii_detector.PRESIDIO_AVAILABLE', False):
            detector = create_pii_detector(config)
            assert detector is None

    def test_pii_detector_init_presidio_unavailable(self):
        """Test PII detector initialization when Presidio is not available."""
        config = PIIDetectionConfig(enabled=True)

        with patch('askrita.utils.pii_detector.PRESIDIO_AVAILABLE', False):
            with pytest.raises(ConfigurationError, match="Presidio analyzer is not available"):
                PIIDetector(config)


class TestPIIDetectorFactory:
    """Test PII detector factory function."""

    def test_create_pii_detector_disabled(self):
        """Test creating PII detector when disabled."""
        config = PIIDetectionConfig(enabled=False)
        detector = create_pii_detector(config)
        assert detector is None

    @patch('askrita.utils.pii_detector.PIIDetector')
    def test_create_pii_detector_enabled(self, mock_detector_class):
        """Test creating PII detector when enabled."""
        config = PIIDetectionConfig(enabled=True)
        mock_detector_instance = Mock()
        mock_detector_class.return_value = mock_detector_instance

        with patch('askrita.utils.pii_detector.PRESIDIO_AVAILABLE', True):
            detector = create_pii_detector(config)
            assert detector == mock_detector_instance
            mock_detector_class.assert_called_once_with(config)

    @patch('askrita.utils.pii_detector.PIIDetector')
    def test_create_pii_detector_initialization_error(self, mock_detector_class):
        """Test creating PII detector when initialization fails."""
        config = PIIDetectionConfig(enabled=True)
        mock_detector_class.side_effect = Exception("Initialization failed")

        with patch('askrita.utils.pii_detector.PRESIDIO_AVAILABLE', True):
            detector = create_pii_detector(config)
            assert detector is None


class TestPIIDetectionResult:
    """Test PII detection result model."""

    def test_pii_detection_result_no_pii(self):
        """Test PII detection result with no PII."""
        result = PIIDetectionResult(
            has_pii=False,
            detected_entities=[],
            confidence_scores=[],
            blocked=False,
            analysis_time_ms=10.5
        )

        assert result.has_pii is False
        assert result.blocked is False
        assert result.entity_count == 0
        assert result.max_confidence == 0.0
        assert result.entity_types == []
        assert result.analysis_time_ms == 10.5

    def test_pii_detection_result_with_pii(self):
        """Test PII detection result with PII detected."""
        entities = [
            {"entity_type": "PERSON", "score": 0.9},
            {"entity_type": "EMAIL_ADDRESS", "score": 0.8}
        ]
        scores = [0.9, 0.8]

        result = PIIDetectionResult(
            has_pii=True,
            detected_entities=entities,
            confidence_scores=scores,
            blocked=True,
            analysis_time_ms=25.3
        )

        assert result.has_pii is True
        assert result.blocked is True
        assert result.entity_count == 2
        assert result.max_confidence == 0.9
        assert set(result.entity_types) == {"PERSON", "EMAIL_ADDRESS"}
        assert result.analysis_time_ms == 25.3


class TestPIISampleDataValidation:
    """Test PII detection in sample data validation."""

    @pytest.fixture
    def mock_database_manager(self):
        """Create mock database manager."""
        db_manager = Mock()
        db_manager.get_sample_data.return_value = {
            "customers": [
                {"id": 1, "name": "John Doe", "email": "john@example.com"},
                {"id": 2, "name": "Jane Smith", "email": "jane@example.com"}
            ],
            "orders": [
                {"order_id": 100, "customer_id": 1, "amount": 250.00},
                {"order_id": 101, "customer_id": 2, "amount": 150.00}
            ]
        }
        return db_manager

    @patch('askrita.utils.pii_detector.PRESIDIO_AVAILABLE', True)
    @patch('askrita.utils.pii_detector.AnalyzerEngine', create=True)
    @patch('askrita.utils.pii_detector.NlpEngineProvider', create=True)
    def test_validate_sample_data_with_pii(self, mock_nlp_provider, mock_analyzer, mock_database_manager):
        """Test sample data validation when PII is found."""
        # Setup mocks
        mock_provider_instance = Mock()
        mock_nlp_engine = Mock()
        mock_provider_instance.create_engine.return_value = mock_nlp_engine
        mock_nlp_provider.return_value = mock_provider_instance

        # Mock PII detection in names
        def mock_analyze(text, entities, language):
            if "John Doe" in text or "Jane Smith" in text:
                mock_result = Mock()
                mock_result.entity_type = "PERSON"
                mock_result.start = 0
                mock_result.end = 8
                mock_result.score = 0.9
                return [mock_result]
            return []

        mock_analyzer_instance = Mock()
        mock_analyzer_instance.analyze.side_effect = mock_analyze
        mock_analyzer.return_value = mock_analyzer_instance

        # Create detector and test
        config = PIIDetectionConfig(enabled=True, validate_sample_data=True)
        detector = PIIDetector(config)

        results = detector.validate_sample_data(mock_database_manager, max_rows=10)

        # Verify results
        assert results["total_tables_checked"] == 2
        assert results["has_pii_violations"] is True
        assert len(results["pii_detections"]) > 0
        assert "customers" in [detection["table"] for detection in results["pii_detections"]]

    @patch('askrita.utils.pii_detector.PRESIDIO_AVAILABLE', True)
    @patch('askrita.utils.pii_detector.AnalyzerEngine', create=True)
    @patch('askrita.utils.pii_detector.NlpEngineProvider', create=True)
    def test_validate_sample_data_no_pii(self, mock_nlp_provider, mock_analyzer, mock_database_manager):
        """Test sample data validation when no PII is found."""
        # Setup mocks
        mock_provider_instance = Mock()
        mock_nlp_engine = Mock()
        mock_provider_instance.create_engine.return_value = mock_nlp_engine
        mock_nlp_provider.return_value = mock_provider_instance

        mock_analyzer_instance = Mock()
        mock_analyzer_instance.analyze.return_value = []  # No PII found
        mock_analyzer.return_value = mock_analyzer_instance

        # Create detector and test
        config = PIIDetectionConfig(enabled=True, validate_sample_data=True)
        detector = PIIDetector(config)

        results = detector.validate_sample_data(mock_database_manager, max_rows=10)

        # Verify results
        assert results["total_tables_checked"] == 2
        assert results["has_pii_violations"] is False
        assert len(results["pii_detections"]) == 0

    def test_validate_sample_data_disabled(self):
        """Test sample data validation when disabled."""
        config = PIIDetectionConfig(enabled=True, validate_sample_data=False)

        with patch('askrita.utils.pii_detector.PRESIDIO_AVAILABLE', True):
            with patch('askrita.utils.pii_detector.AnalyzerEngine', create=True):
                with patch('askrita.utils.pii_detector.NlpEngineProvider', create=True):
                    detector = PIIDetector(config)

                    mock_db_manager = Mock()
                    results = detector.validate_sample_data(mock_db_manager)

                    assert results["skipped"] is True
                    assert results["reason"] == "Sample data validation disabled"


class TestPIIDetectionIntegration:
    """Integration tests for PII detection in workflow."""

    def test_pii_detection_workflow_integration(self):
        """Test PII detection integration with workflow configuration."""
        from askrita.config_manager import ConfigManager

        # Create test configuration with PII detection enabled
        config_data = {
            "database": {"connection_string": "sqlite:///test.db"},
            "llm": {"provider": "openai", "model": "gpt-4o"},
            "workflow": {"steps": {"pii_detection": True}},
            "pii_detection": {
                "enabled": True,
                "block_on_detection": True,
                "entities": ["PERSON", "EMAIL_ADDRESS"]
            }
        }

        # Test configuration loading with validation mocked
        with patch.object(ConfigManager, 'load_config'):
            with patch.object(ConfigManager, 'validate_config', return_value=True):
                config_manager = ConfigManager()
                config_manager._config_data = config_data

                pii_config = config_manager.pii_detection
                assert pii_config.enabled is True
                assert pii_config.block_on_detection is True
                assert "PERSON" in pii_config.entities
                assert "EMAIL_ADDRESS" in pii_config.entities


if __name__ == "__main__":
    pytest.main([__file__])
