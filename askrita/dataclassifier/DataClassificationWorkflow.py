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
#   langchain-core (MIT)
#   pandas (BSD-3-Clause)

"""Data Classification Workflow for processing and classifying data using LLMs."""

import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

import pandas as pd
from langchain_core.prompts import ChatPromptTemplate

from ..config_manager import ConfigManager, get_config
from ..exceptions import ConfigurationError, LLMError
from ..utils.LLMManager import LLMManager
from .DataProcessor import DataProcessor
from .Models import create_dynamic_classification_model

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Workflow step and config-section name constants (used 3+ times)
# ---------------------------------------------------------------------------
_CFG_DATA_PROCESSING = "data_processing"
_CFG_CLASSIFICATION = "classification"
_CFG_WORKFLOW = "data_classification_workflow"
_STEP_LOAD_DATA = "load_data"
_STEP_PREPROCESS_DATA = "preprocess_data"
_STEP_CLASSIFY_DATA = "classify_data"
_STEP_POSTPROCESS_RESULTS = "postprocess_results"
_STEP_SAVE_RESULTS = "save_results"


class DataClassificationWorkflow:
    """
    Unified Data Classification Workflow that handles data processing and LLM-based classification.

    This workflow:
    1. Loads data from Excel/CSV files
    2. Preprocesses and cleans the data
    3. Uses LLM with structured output for classification
    4. Saves results back to files

    Reuses existing LLMManager for consistent LLM handling and configuration.
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize DataClassificationWorkflow with configuration.

        Args:
            config_manager: Optional ConfigManager instance. If None, uses global config.
        """
        self.config = config_manager or get_config()
        self._temp_files = []  # Track temporary files for cleanup

        # Initialize components - reusing existing LLMManager
        self.llm_manager = LLMManager(self.config)
        self.data_processor = DataProcessor(self.config)

        # Get configuration for this workflow
        self.data_processing_config = self.config.data_processing
        self.classification_config = self.config.classification
        self.workflow_config = self.config.data_classification_workflow

        # Setup structured LLM based on model type (if field_definitions are available)
        try:
            self._setup_structured_llm()
            logger.info("DataClassificationWorkflow initialized with structured LLM")
        except ConfigurationError:
            # Field definitions not provided yet - will be set up when classification is configured
            # This is expected behavior for runtime configuration
            logger.debug(
                "Structured LLM will be configured when classification settings are provided at runtime"
            )
            self.structured_llm = None  # Will be set during configure_classification
        except LLMError as e:
            # Unexpected LLM setup error - re-raise
            logger.error(f"Failed to initialize DataClassificationWorkflow: {e}")
            raise

        logger.info("DataClassificationWorkflow initialized successfully")

    def configure_data_processing(
        self,
        input_data: Optional[pd.DataFrame] = None,
        input_file_path: Optional[str] = None,
        output_file_path: Optional[str] = None,
        feedback_columns: Optional[List[str]] = None,
        max_rows: Optional[int] = None,
        batch_size: Optional[int] = None,
        output_format: Optional[str] = None,
        skip_empty_rows: Optional[bool] = None,
    ) -> "DataClassificationWorkflow":
        """
        Configure data processing settings at runtime.

        Args:
            input_data: DataFrame to process (alternative to input_file_path)
            input_file_path: Path to input file
            output_file_path: Path to output file
            feedback_columns: List of text columns to analyze
            max_rows: Maximum rows to process (0 = no limit)
            batch_size: Batch size for processing
            output_format: Output format (json, csv, excel)
            skip_empty_rows: Whether to skip empty rows

        Returns:
            Self for method chaining
        """

        # Handle DataFrame input by creating temporary file
        if input_data is not None:
            if not input_file_path:
                temp_file = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
                input_data.to_csv(temp_file.name, index=False)
                input_file_path = temp_file.name
                self._temp_files.append(temp_file.name)
                logger.info(f"Created temporary input file: {temp_file.name}")

        # Update configuration data directly
        if _CFG_DATA_PROCESSING not in self.config._config_data:
            self.config._config_data[_CFG_DATA_PROCESSING] = {}

        data_config = self.config._config_data[_CFG_DATA_PROCESSING]

        # Update provided values
        if input_file_path is not None:
            data_config["input_file_path"] = input_file_path
        if output_file_path is not None:
            data_config["output_file_path"] = output_file_path
        if feedback_columns is not None:
            data_config["feedback_columns"] = feedback_columns
        if max_rows is not None:
            data_config["max_rows_to_process"] = max_rows
        if batch_size is not None:
            data_config["batch_size"] = batch_size
        if output_format is not None:
            data_config["output_format"] = output_format
        if skip_empty_rows is not None:
            data_config["skip_empty_rows"] = skip_empty_rows

        # Refresh cached configuration
        self._refresh_data_processing_config()

        logger.info("Data processing configuration updated")
        return self

    def configure_classification(
        self,
        model_type: Optional[str] = None,
        system_prompt: Optional[str] = None,
        field_definitions: Optional[Dict[str, Dict[str, Any]]] = None,
        analysis_columns: Optional[List[str]] = None,
        enable_batch_processing: Optional[bool] = None,
    ) -> "DataClassificationWorkflow":
        """
        Configure classification settings at runtime.

        Args:
            model_type: Type of classification model
            system_prompt: Custom system prompt
            field_definitions: Dynamic field definitions for structured output
            analysis_columns: Columns to include in analysis
            enable_batch_processing: Whether to enable batch processing

        Returns:
            Self for method chaining
        """

        # Update configuration data directly
        if _CFG_CLASSIFICATION not in self.config._config_data:
            self.config._config_data[_CFG_CLASSIFICATION] = {}

        classification_config = self.config._config_data[_CFG_CLASSIFICATION]

        # Update provided values
        if model_type is not None:
            classification_config["model_type"] = model_type
        if system_prompt is not None:
            classification_config["system_prompt"] = system_prompt
        if field_definitions is not None:
            classification_config["field_definitions"] = field_definitions
        if analysis_columns is not None:
            classification_config["analysis_columns"] = analysis_columns
        if enable_batch_processing is not None:
            classification_config["enable_batch_processing"] = enable_batch_processing

        # Refresh cached configuration and re-setup structured LLM
        self._refresh_classification_config()

        logger.info("Classification configuration updated")
        return self

    def configure_workflow_steps(
        self,
        steps: Optional[Dict[str, bool]] = None,
        max_retries: Optional[int] = None,
        timeout_per_step: Optional[int] = None,
    ) -> "DataClassificationWorkflow":
        """
        Configure which workflow steps to execute.

        Args:
            steps: Dictionary of step names and whether to enable them
            max_retries: Maximum number of retries for failed steps
            timeout_per_step: Timeout per step in seconds

        Returns:
            Self for method chaining
        """

        # Update configuration data directly
        if _CFG_WORKFLOW not in self.config._config_data:
            self.config._config_data[_CFG_WORKFLOW] = {}

        workflow_config = self.config._config_data[_CFG_WORKFLOW]

        # Set default steps if none provided
        if steps is None:
            steps = {
                _STEP_LOAD_DATA: True,
                _STEP_PREPROCESS_DATA: True,
                _STEP_CLASSIFY_DATA: True,
                _STEP_POSTPROCESS_RESULTS: True,
                _STEP_SAVE_RESULTS: True,
            }

        # Update provided values
        if steps is not None:
            if "steps" not in workflow_config:
                workflow_config["steps"] = {}
            workflow_config["steps"].update(steps)
        if max_retries is not None:
            workflow_config["max_retries"] = max_retries
        if timeout_per_step is not None:
            workflow_config["timeout_per_step"] = timeout_per_step

        # Refresh cached configuration
        self._refresh_workflow_config()

        logger.info("Workflow configuration updated")
        return self

    def set_field_definitions(
        self, field_definitions: Dict[str, Dict[str, Any]]
    ) -> "DataClassificationWorkflow":
        """
        Set field definitions for dynamic classification model.

        Args:
            field_definitions: Dictionary defining fields and their types/constraints

        Returns:
            Self for method chaining
        """
        return self.configure_classification(field_definitions=field_definitions)

    def set_input_dataframe(
        self,
        df: pd.DataFrame,
        feedback_columns: List[str],
        output_path: Optional[str] = None,
    ) -> "DataClassificationWorkflow":
        """
        Set input DataFrame directly for processing.

        Args:
            df: DataFrame to process
            feedback_columns: List of text columns to analyze
            output_path: Optional output path for results

        Returns:
            Self for method chaining
        """
        return self.configure_data_processing(
            input_data=df,
            feedback_columns=feedback_columns,
            output_file_path=output_path,
        )

    def _refresh_data_processing_config(self):
        """Refresh cached data processing configuration."""
        self.data_processing_config = self.config.data_processing
        # Re-initialize data processor with updated config
        self.data_processor = DataProcessor(self.config)

    def _refresh_classification_config(self):
        """Refresh cached classification configuration and re-setup structured LLM."""
        self.classification_config = self.config.classification
        # Re-setup structured LLM with new configuration
        if self.classification_config.field_definitions:
            try:
                self._setup_structured_llm()
                logger.info(
                    "Structured LLM configured successfully with runtime field definitions"
                )
            except Exception as e:
                logger.error(
                    f"Failed to setup structured LLM with runtime configuration: {e}"
                )
                raise

    def _refresh_workflow_config(self):
        """Refresh cached workflow configuration."""
        self.workflow_config = self.config.data_classification_workflow

    def cleanup_temp_files(self):
        """Clean up any temporary files created during processing."""
        for temp_file in self._temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    logger.debug(f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")
        self._temp_files.clear()

    def _setup_structured_llm(self):
        """Setup LLM with structured output based on configuration."""
        try:
            model_type = self.classification_config.model_type

            # Get field definitions from config - these MUST be provided
            field_definitions = self.classification_config.field_definitions

            if not field_definitions:
                # Don't log as error - this is expected for runtime configuration
                raise ConfigurationError(
                    f"No field_definitions provided in configuration for model type '{model_type}'. "
                    "Field definitions are required and must be specified in the 'classification.field_definitions' "
                    "section of your configuration file, or configured at runtime using configure_classification()."
                )

            logger.info(
                f"Using field definitions from configuration: {list(field_definitions.keys())}"
            )

            # Validate that we have at least one field defined
            if len(field_definitions) == 0:
                raise ConfigurationError(
                    "Field definitions dictionary is empty. At least one field must be defined for classification."
                )

            # Create dynamic model based on field definitions
            model_name = f"{model_type.title().replace('_', '')}Model"
            self.output_model = create_dynamic_classification_model(
                field_definitions=field_definitions, model_name=model_name
            )

            # Setup structured LLM with the dynamic model
            self.structured_llm = self.llm_manager.llm.with_structured_output(
                self.output_model
            )

            logger.info(
                f"Successfully configured LLM with dynamic model '{model_name}' for {model_type}"
            )

        except ConfigurationError as e:
            # For configuration errors (like missing field_definitions), don't log as error
            # This is expected behavior in runtime configuration scenarios
            raise e
        except Exception as e:
            # Only log unexpected errors as errors
            logger.error(f"Failed to setup structured LLM: {e}")
            raise LLMError(f"Structured LLM setup failed: {str(e)}")

    def get_system_prompt(self) -> str:
        """
        Get system prompt for classification.

        Returns:
            System prompt string
        """
        # Use prompt from config if provided, otherwise use default
        config_prompt = self.classification_config.system_prompt

        if config_prompt:
            return config_prompt

        # Default prompts based on model type
        if self.classification_config.model_type == "customer_feedback":
            return """
As a data analyst for a healthcare services company, you are tasked with analyzing customer feedback regarding vendors conducting in-home patient visits.

The feedback highlights several key concerns, including vendors failing to show up for scheduled appointments, frequent cancellations, poor customer service, and unprofessional or rude behavior toward patients. These recurring issues—such as vendor no-shows, cancellations, and negative interactions—need further investigation to improve the overall patient experience.

Classify as Other if the feedback does not fall into any of the predefined categories.
"""
        else:  # general classification
            return """
You are a data analyst tasked with classifying and analyzing data.
Categorize the content accurately and provide meaningful insights.
Classify as appropriate categories based on the content provided.
"""

    def classify_single_row(self, feedback_text: str) -> Optional[Dict[str, Any]]:
        """
        Classify a single row of feedback text.

        Args:
            feedback_text: Combined feedback text to classify

        Returns:
            Dictionary with classification results, or None if classification fails
        """
        if not feedback_text.strip():
            logger.warning("Empty feedback text provided, skipping classification")
            return None

        # Check if structured LLM is set up
        if self.structured_llm is None:
            raise ConfigurationError(
                "Classification not configured. Please call configure_classification() "
                "with field_definitions before attempting to classify data."
            )

        try:
            # Create prompt with system context and feedback
            system_prompt = self.get_system_prompt()

            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", system_prompt),
                    ("human", "Customer Feedback:\\n{feedback}"),
                ]
            )

            # Format the prompt and invoke structured LLM
            messages = prompt.format_messages(feedback=feedback_text)
            response = self.structured_llm.invoke(messages)

            # Convert Pydantic model to dictionary
            if hasattr(response, "model_dump"):
                return response.model_dump()
            else:
                return dict(response)

        except Exception as e:
            logger.warning(f"Classification failed for text: {str(e)}")
            return None

    def _classify_dataframe_row(self, row, index, analysis_columns: list) -> dict:
        """Classify a single DataFrame row and return the result dict."""
        combined_feedback = self.data_processor.combine_feedback_text(row)
        result = row.to_dict()
        if not combined_feedback.strip():
            logger.warning(f"Empty feedback at index {index}, skipping classification")
            return result
        classification_result = self.classify_single_row(combined_feedback)
        if classification_result:
            for column in analysis_columns:
                if column in classification_result:
                    result[column] = classification_result[column]
                else:
                    logger.warning(f"Missing '{column}' in classification result for index {index}")
                    result[column] = None
        else:
            for column in analysis_columns:
                result[column] = None
        return result

    def process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process entire DataFrame with classification.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with classification results added
        """
        logger.info(f"Starting classification of {len(df)} rows")

        results_list = []
        analysis_columns = self.classification_config.analysis_columns

        # Process data in batches if enabled
        for batch_idx, batch_df in enumerate(self.data_processor.create_batches(df)):
            logger.info(f"Processing batch {batch_idx + 1}")
            for index, row in batch_df.iterrows():
                result = self._classify_dataframe_row(row, index, analysis_columns)
                results_list.append(result)
                if (len(results_list) % 100) == 0:
                    logger.info(f"Processed {len(results_list)} rows...")

        # Convert results to DataFrame
        results_df = pd.DataFrame(results_list)
        logger.info(f"Classification completed for {len(results_df)} rows")

        return results_df

    def run_workflow(
        self,
        input_file_path: Optional[str] = None,
        output_file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run the complete data classification workflow.

        Args:
            input_file_path: Optional input file path (overrides config)
            output_file_path: Optional output file path (overrides config)

        Returns:
            Dictionary with workflow results and statistics
        """
        try:
            logger.info("🚀 Starting Data Classification Workflow")

            # Step 1: Load data
            if self.workflow_config.steps.get(_STEP_LOAD_DATA, True):
                logger.info("📂 Step 1: Loading data...")
                df = self.data_processor.load_data(input_file_path)
                self.data_processor.validate_input_data(df)
                original_df = df.copy()
            else:
                raise ConfigurationError("load_data step is disabled but required")

            # Step 2: Preprocess data
            if self.workflow_config.steps.get(_STEP_PREPROCESS_DATA, True):
                logger.info("🧹 Step 2: Preprocessing data...")
                df = self.data_processor.preprocess_data(df)

            # Step 3: Classify data
            if self.workflow_config.steps.get(_STEP_CLASSIFY_DATA, True):
                logger.info("🤖 Step 3: Classifying data with LLM...")
                df = self.process_dataframe(df)
            else:
                logger.warning("classify_data step is disabled")

            # Step 4: Postprocess results (placeholder for future enhancements)
            if self.workflow_config.steps.get(_STEP_POSTPROCESS_RESULTS, True):
                logger.info("📊 Step 4: Postprocessing results...")
                # Future: Add result validation, aggregation, etc.

            # Step 5: Save results
            if self.workflow_config.steps.get(_STEP_SAVE_RESULTS, True):
                logger.info("💾 Step 5: Saving results...")
                output_path = self.data_processor.save_results(df, output_file_path)
            else:
                output_path = None
                logger.warning("save_results step is disabled")

            # Generate statistics
            stats = self.data_processor.get_processing_stats(original_df, df)

            results = {
                "status": "success",
                "output_path": output_path,
                "statistics": stats,
                "processed_data": df,  # Include DataFrame for immediate use
            }

            logger.info("✅ Data Classification Workflow completed successfully!")
            return results

        except Exception as e:
            logger.error(f"❌ Workflow failed: {e}")
            return {"status": "failed", "error": str(e), "statistics": None}

    def classify_text(self, text: str) -> Dict[str, Any]:
        """
        Classify a single piece of text (convenience method).

        Args:
            text: Text to classify

        Returns:
            Classification results
        """
        result = self.classify_single_row(text)
        if result is None:
            raise LLMError("Text classification failed")
        return result

    def get_workflow_info(self) -> Dict[str, Any]:
        """
        Get information about the current workflow configuration.

        Returns:
            Dictionary with workflow configuration details
        """
        return {
            "workflow_type": "data_classification",
            "llm_provider": self.config.llm.provider,
            "llm_model": self.config.llm.model,
            "classification_model_type": self.classification_config.model_type,
            "enabled_steps": {k: v for k, v in self.workflow_config.steps.items() if v},
            _CFG_DATA_PROCESSING: {
                "input_file": self.data_processing_config.input_file_path,
                "output_file": self.data_processing_config.output_file_path,
                "feedback_columns": self.data_processing_config.feedback_columns,
                "max_rows": self.data_processing_config.max_rows_to_process,
                "batch_size": self.data_processing_config.batch_size,
                "output_format": self.data_processing_config.output_format,
            },
        }

    def process_texts(
        self, texts: List[str], return_dataframe: bool = True
    ) -> Dict[str, Any]:
        """
        Process a list of texts directly without file I/O.

        Args:
            texts: List of text strings to classify
            return_dataframe: Whether to include DataFrame in results

        Returns:
            Dictionary with classification results
        """
        # Create DataFrame from texts
        df = pd.DataFrame({"text": texts})

        # Configure to use the text column with temporary output
        temp_output = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._temp_files.append(temp_output.name)
        temp_output.close()

        self.configure_data_processing(
            input_data=df,
            feedback_columns=["text"],
            output_format="json",
            output_file_path=temp_output.name,
        )

        # Configure workflow to disable save_results for text processing
        self.configure_workflow_steps(
            steps={
                _STEP_LOAD_DATA: True,
                _STEP_PREPROCESS_DATA: True,
                _STEP_CLASSIFY_DATA: True,
                _STEP_POSTPROCESS_RESULTS: True,
                _STEP_SAVE_RESULTS: False,  # Disable saving for direct text processing
            }
        )

        # Run workflow
        result = self.run_workflow()

        # Include DataFrame if requested
        if return_dataframe and result.get("status") == "success":
            result["results_list"] = result.get(
                "processed_data", pd.DataFrame()
            ).to_dict("records")

        return result

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup temporary files."""
        self.cleanup_temp_files()

    def __del__(self):
        """Destructor - cleanup temporary files."""
        try:
            self.cleanup_temp_files()
        except Exception:
            # Silently ignore cleanup errors during garbage collection
            pass
