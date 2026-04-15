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
#   presidio-analyzer (MIT)
#   spacy (MIT)

"""
PHI/PII Detection module using Microsoft Presidio analyzer.

This module provides privacy protection by detecting personally identifiable information
(PII) and protected health information (PHI) in user queries and database sample data.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    PRESIDIO_AVAILABLE = True
except ImportError:
    PRESIDIO_AVAILABLE = False

from ..config_manager import PIIDetectionConfig
from ..exceptions import ConfigurationError, ValidationError

logger = logging.getLogger(__name__)


@dataclass
class PIIDetectionResult:
    """Result of PII detection analysis."""

    has_pii: bool
    detected_entities: List[Dict[str, Any]]
    confidence_scores: List[float]
    blocked: bool
    analysis_time_ms: float
    redacted_text: Optional[str] = None

    def __post_init__(self):
        """Calculate summary statistics after initialization."""
        self.entity_count = len(self.detected_entities)
        self.max_confidence = (
            max(self.confidence_scores) if self.confidence_scores else 0.0
        )
        self.entity_types = list(
            {entity.get("entity_type", "UNKNOWN") for entity in self.detected_entities}
        )


class PIIDetector:
    """
    PHI/PII detector using Microsoft Presidio analyzer.

    This class provides methods to detect personally identifiable information
    and protected health information in text data to ensure privacy compliance.
    """

    def __init__(self, config: PIIDetectionConfig):
        """
        Initialize PII detector with configuration.

        Args:
            config: PIIDetectionConfig instance with detection settings

        Raises:
            ConfigurationError: If Presidio is not available or config is invalid
        """
        if not PRESIDIO_AVAILABLE:
            raise ConfigurationError(
                "Presidio analyzer is not available. Please install it with: "
                "pip install presidio-analyzer"
            )

        self.config = config
        self._validate_config()

        # Initialize Presidio analyzer
        try:
            # Create NLP engine provider for the specified language
            nlp_configuration = {
                "nlp_engine_name": "spacy",
                "models": [
                    {
                        "lang_code": config.language,
                        "model_name": f"{config.language}_core_web_sm",
                    }
                ],
            }

            # Create NLP engine provider
            provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
            nlp_engine = provider.create_engine()

            # Create analyzer engine
            self.analyzer = AnalyzerEngine(
                nlp_engine=nlp_engine, supported_languages=[config.language]
            )

            # Set up audit logging if configured
            self._setup_audit_logging()

            logger.info(
                f"✅ PII detector initialized with {len(config.entities)} entity types"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Presidio analyzer: {e}")
            raise ConfigurationError(f"PII detector initialization failed: {e}")

    def _validate_config(self) -> None:
        """Validate PII detection configuration."""
        if not self.config.entities:
            raise ConfigurationError("PII detection entities list cannot be empty")

        if not 0.0 <= self.config.confidence_threshold <= 1.0:
            raise ConfigurationError(
                "PII confidence threshold must be between 0.0 and 1.0"
            )

        if self.config.sample_data_rows < 1:
            raise ConfigurationError("Sample data rows must be at least 1")

        if self.config.sample_data_timeout < 1:
            raise ConfigurationError("Sample data timeout must be at least 1 second")

    def _setup_audit_logging(self) -> None:
        """Setup audit logging for PII detection if configured."""
        if self.config.audit_log_path and self.config.log_pii_attempts:
            try:
                # Create audit logger
                audit_logger = logging.getLogger("askrita.pii_audit")
                audit_handler = logging.FileHandler(self.config.audit_log_path)
                audit_formatter = logging.Formatter(
                    "%(asctime)s - PII_AUDIT - %(levelname)s - %(message)s"
                )
                audit_handler.setFormatter(audit_formatter)
                audit_logger.addHandler(audit_handler)
                audit_logger.setLevel(logging.INFO)

                self.audit_logger = audit_logger
                logger.info(
                    f"📋 PII audit logging enabled: {self.config.audit_log_path}"
                )

            except Exception as e:
                logger.warning(f"Failed to setup PII audit logging: {e}")
                self.audit_logger = None
        else:
            self.audit_logger = None

    def detect_pii_in_text(
        self, text: str, context: str = "user_query"
    ) -> PIIDetectionResult:
        """
        Detect PII/PHI in the given text.

        Args:
            text: Text to analyze for PII
            context: Context description for logging (e.g., "user_query", "sample_data")

        Returns:
            PIIDetectionResult with detection details
        """
        start_time = time.time()

        try:
            # Run Presidio analysis
            results = self.analyzer.analyze(
                text=text, entities=self.config.entities, language=self.config.language
            )

            # Filter results by confidence threshold
            filtered_results = [
                result
                for result in results
                if result.score >= self.config.confidence_threshold
            ]

            # Extract detection information
            detected_entities = []
            confidence_scores = []

            for result in filtered_results:
                entity_info = {
                    "entity_type": result.entity_type,
                    "start": result.start,
                    "end": result.end,
                    "score": result.score,
                    "text_snippet": (
                        text[result.start : result.end]
                        if not self.config.redact_in_logs
                        else "[REDACTED]"
                    ),
                }
                detected_entities.append(entity_info)
                confidence_scores.append(result.score)

            # Determine if query should be blocked
            has_pii = len(filtered_results) > 0
            blocked = has_pii and self.config.block_on_detection

            # Calculate analysis time
            analysis_time_ms = (time.time() - start_time) * 1000

            # Create redacted text if needed
            redacted_text = (
                self._create_redacted_text(text, filtered_results) if has_pii else None
            )

            # Create result
            result = PIIDetectionResult(
                has_pii=has_pii,
                detected_entities=detected_entities,
                confidence_scores=confidence_scores,
                blocked=blocked,
                analysis_time_ms=analysis_time_ms,
                redacted_text=redacted_text,
            )

            # Log audit information
            self._log_audit_event(
                context,
                result,
                text if not self.config.redact_in_logs else "[REDACTED]",
            )

            return result

        except Exception as e:
            logger.error(f"PII detection failed: {e}")
            raise ValidationError(f"PII analysis failed: {str(e)}")

    def _create_redacted_text(self, text: str, results: List[Any]) -> str:
        """Create redacted version of text with PII entities masked."""
        if not results:
            return text

        # Sort results by start position (reverse order to maintain indices)
        sorted_results = sorted(results, key=lambda x: x.start, reverse=True)

        redacted_text = text
        for result in sorted_results:
            # Replace detected PII with entity type placeholder
            placeholder = f"[{result.entity_type}]"
            redacted_text = (
                redacted_text[: result.start]
                + placeholder
                + redacted_text[result.end :]
            )

        return redacted_text

    def _log_audit_event(
        self, context: str, result: PIIDetectionResult, original_text: str
    ) -> None:
        """Log PII detection audit event."""
        if not self.config.log_pii_attempts:
            return

        audit_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context": context,
            "has_pii": result.has_pii,
            "entity_count": result.entity_count,
            "entity_types": result.entity_types,
            "max_confidence": result.max_confidence,
            "blocked": result.blocked,
            "analysis_time_ms": result.analysis_time_ms,
            "text_length": len(original_text),
        }

        if self.audit_logger:
            self.audit_logger.info(f"PII_DETECTION: {audit_data}")
        else:
            logger.info(f"PII Detection Audit: {audit_data}")

    def _scan_table_rows_for_pii(
        self,
        table_name: str,
        table_data: list,
        sample_rows: int,
        start_time: float,
        validation_results: dict,
    ) -> bool:
        """Scan rows in a single table for PII. Returns True if timed out."""
        rows_checked = 0
        for row in table_data:
            if rows_checked >= sample_rows:
                break
            row_text = " ".join(str(v) for v in row.values() if v is not None)
            pii_result = self.detect_pii_in_text(
                row_text, context=f"sample_data_table_{table_name}"
            )
            if pii_result.has_pii:
                validation_results["tables_with_pii"].append(table_name)
                validation_results["pii_detections"].append(
                    {
                        "table": table_name,
                        "row_index": rows_checked,
                        "entity_types": pii_result.entity_types,
                        "max_confidence": pii_result.max_confidence,
                        "entity_count": pii_result.entity_count,
                    }
                )
                validation_results["has_pii_violations"] = True
            rows_checked += 1
            validation_results["total_rows_checked"] += 1
            if time.time() - start_time > self.config.sample_data_timeout:
                logger.warning(
                    f"Sample data validation timeout after {self.config.sample_data_timeout}s"
                )
                return True
        return False

    def validate_sample_data(
        self, database_manager, max_rows: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Validate database sample data for PII/PHI content.

        Args:
            database_manager: DatabaseManager instance to fetch sample data
            max_rows: Maximum rows to sample (overrides config if provided)

        Returns:
            Dictionary with validation results and statistics
        """
        if not self.config.validate_sample_data:
            return {"skipped": True, "reason": "Sample data validation disabled"}

        sample_rows = max_rows or self.config.sample_data_rows
        start_time = time.time()

        try:
            logger.info(
                f"🔍 Validating database sample data for PII (max {sample_rows} rows)"
            )

            # Get sample data from database
            sample_data = database_manager.get_sample_data(limit=sample_rows)

            validation_results = {
                "total_tables_checked": 0,
                "total_rows_checked": 0,
                "tables_with_pii": [],
                "pii_detections": [],
                "validation_time_ms": 0,
                "has_pii_violations": False,
            }

            # Check each table's sample data
            for table_name, table_data in sample_data.items():
                validation_results["total_tables_checked"] += 1
                timed_out = self._scan_table_rows_for_pii(
                    table_name, table_data, sample_rows, start_time, validation_results
                )
                if timed_out:
                    break

            validation_results["validation_time_ms"] = (time.time() - start_time) * 1000

            # Log summary
            if validation_results["has_pii_violations"]:
                logger.warning(
                    f"⚠️  PII detected in database sample data! "
                    f"Tables affected: {len(set(validation_results['tables_with_pii']))}, "
                    f"Total detections: {len(validation_results['pii_detections'])}"
                )
            else:
                logger.info(
                    f"✅ No PII detected in {validation_results['total_rows_checked']} sample rows"
                )

            return validation_results

        except Exception as e:
            logger.error(f"Sample data PII validation failed: {e}")
            return {
                "error": str(e),
                "validation_time_ms": (time.time() - start_time) * 1000,
                "has_pii_violations": False,  # Assume no violations on error
            }


def create_pii_detector(config: PIIDetectionConfig) -> Optional[PIIDetector]:
    """
    Factory function to create PII detector instance.

    Args:
        config: PII detection configuration

    Returns:
        PIIDetector instance or None if disabled/unavailable
    """
    if not config.enabled:
        logger.debug("PII detection is disabled in configuration")
        return None

    if not PRESIDIO_AVAILABLE:
        logger.warning(
            "PII detection is enabled but Presidio analyzer is not available. "
            "Install with: pip install presidio-analyzer"
        )
        return None

    try:
        return PIIDetector(config)
    except Exception as e:
        logger.error(f"Failed to create PII detector: {e}")
        return None


# Export public interface
__all__ = [
    "PIIDetector",
    "PIIDetectionResult",
    "create_pii_detector",
    "PRESIDIO_AVAILABLE",
]
