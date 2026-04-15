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
#   pandas (BSD-3-Clause)

"""Data processing utilities for classification workflows."""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Generator, Optional

import pandas as pd

from ..config_manager import ConfigManager
from ..exceptions import ConfigurationError, ValidationError

logger = logging.getLogger(__name__)


class DataProcessor:
    """
    Handles data loading, processing, and saving for classification workflows.

    This class provides utilities for:
    - Loading data from Excel, CSV files
    - Preprocessing and cleaning data
    - Batch processing for large datasets
    - Saving results in various formats
    """

    def __init__(self, config_manager: ConfigManager):
        """
        Initialize DataProcessor with configuration.

        Args:
            config_manager: ConfigManager instance with data processing settings
        """
        self.config = config_manager
        self.data_processing_config = config_manager.data_processing
        self.classification_config = config_manager.classification

    def load_data(self, file_path: Optional[str] = None) -> pd.DataFrame:
        """
        Load data from file.

        Args:
            file_path: Path to data file. If None, uses config setting.

        Returns:
            Loaded DataFrame

        Raises:
            ConfigurationError: If file path is not provided and not in config
            FileNotFoundError: If specified file doesn't exist
            ValidationError: If file format is not supported
        """
        input_path = file_path or self.data_processing_config.input_file_path

        if not input_path:
            raise ConfigurationError(
                "Input file path not provided. Set it in config 'data_processing.input_file_path' "
                "or pass it as parameter."
            )

        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        file_extension = Path(input_path).suffix.lower()

        try:
            logger.info(f"Loading data from: {input_path}")

            if file_extension in [".xlsx", ".xls"]:
                df = pd.read_excel(input_path)
            elif file_extension == ".csv":
                # Use configurable CSV parameters
                csv_params = self._get_csv_parameters()
                logger.info(f"Loading CSV with parameters: {csv_params}")
                df = pd.read_csv(input_path, **csv_params)
            else:
                raise ValidationError(f"Unsupported file format: {file_extension}")

            logger.info(f"Loaded {len(df)} rows and {len(df.columns)} columns")
            return df

        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            raise ValidationError(f"Data loading failed: {str(e)}")

    def preprocess_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess the data before classification.

        Args:
            df: Input DataFrame

        Returns:
            Preprocessed DataFrame
        """
        logger.info("Preprocessing data...")

        # Fill NaN values with empty strings for clean processing
        df = df.fillna("")

        # Filter out empty rows if configured
        if self.data_processing_config.skip_empty_rows:
            feedback_columns = self.data_processing_config.feedback_columns

            # Check if any of the feedback columns have content
            mask = False
            for col in feedback_columns:
                if col in df.columns:
                    mask |= df[col].astype(str).str.strip() != ""

            if isinstance(mask, pd.Series):
                df = df[mask]
                logger.info(f"Filtered out empty rows, {len(df)} rows remaining")

        # Limit number of rows if configured
        max_rows = self.data_processing_config.max_rows_to_process
        if max_rows > 0 and len(df) > max_rows:
            df = df.head(max_rows)
            logger.info(f"Limited processing to {max_rows} rows")

        return df

    def combine_feedback_text(self, row: pd.Series) -> str:
        """
        Combine text from multiple feedback columns into a single string.

        Args:
            row: DataFrame row

        Returns:
            Combined feedback text
        """
        feedback_columns = self.data_processing_config.feedback_columns
        combined_text = ""

        for column in feedback_columns:
            if column in row.index:
                text = str(row[column]).strip()
                if text and text.lower() != "nan":
                    combined_text += f"{text}\\n"

        return combined_text.strip()

    def create_batches(self, df: pd.DataFrame) -> Generator[pd.DataFrame, None, None]:
        """
        Create batches from DataFrame for batch processing.

        Args:
            df: Input DataFrame

        Yields:
            DataFrame batches
        """
        batch_size = self.data_processing_config.batch_size

        if not self.classification_config.enable_batch_processing:
            # Process all data as a single batch
            yield df
            return

        logger.info(f"Creating batches of size {batch_size}")

        for start_idx in range(0, len(df), batch_size):
            end_idx = min(start_idx + batch_size, len(df))
            batch = df.iloc[start_idx:end_idx].copy()

            logger.info(
                f"Processing batch {start_idx // batch_size + 1}: rows {start_idx}-{end_idx-1}"
            )
            yield batch

    def save_results(self, df: pd.DataFrame, output_path: Optional[str] = None) -> str:
        """
        Save results to file.

        Args:
            df: DataFrame with results
            output_path: Output file path. If None, uses config setting.

        Returns:
            Path where results were saved

        Raises:
            ConfigurationError: If output path is not provided and not in config
            ValidationError: If output format is not supported
        """
        save_path = output_path or self.data_processing_config.output_file_path

        if not save_path:
            raise ConfigurationError(
                "Output file path not provided. Set it in config 'data_processing.output_file_path' "
                "or pass it as parameter."
            )

        # Create output directory if it doesn't exist
        output_dir = Path(save_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        output_format = self.data_processing_config.output_format

        try:
            logger.info(f"Saving results to: {save_path}")

            if output_format == "excel":
                df.to_excel(save_path, index=False)
            elif output_format == "csv":
                df.to_csv(save_path, index=False)
            elif output_format == "json":
                # Use more robust JSON saving approach
                try:
                    df.to_json(save_path, orient="records", indent=2)
                except Exception as json_error:
                    # Fallback: manually write JSON using standard library
                    import json

                    records = df.to_dict("records")
                    with open(save_path, "w", encoding="utf-8") as f:
                        json.dump(records, f, indent=2, ensure_ascii=False)
                    logger.info(
                        f"Used fallback JSON writing method due to: {json_error}"
                    )
            else:
                raise ValidationError(f"Unsupported output format: {output_format}")

            logger.info(f"Successfully saved {len(df)} rows to {save_path}")
            return save_path

        except Exception as e:
            logger.error(f"Failed to save results: {e}")
            raise ValidationError(f"Results saving failed: {str(e)}")

    def validate_input_data(self, df: pd.DataFrame) -> bool:
        """
        Validate that input data has required columns.

        Args:
            df: Input DataFrame

        Returns:
            True if validation passes

        Raises:
            ValidationError: If validation fails
        """
        feedback_columns = self.data_processing_config.feedback_columns
        missing_columns = [col for col in feedback_columns if col not in df.columns]

        if missing_columns:
            available_columns = list(df.columns)
            raise ValidationError(
                f"Missing required feedback columns: {missing_columns}\\n"
                f"Available columns: {available_columns}"
            )

        if len(df) == 0:
            raise ValidationError("Input data is empty")

        logger.info("Input data validation passed")
        return True

    def get_processing_stats(
        self, original_df: pd.DataFrame, processed_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Get statistics about data processing.

        Args:
            original_df: Original DataFrame before processing
            processed_df: DataFrame after processing

        Returns:
            Dictionary with processing statistics
        """
        return {
            "original_rows": len(original_df),
            "processed_rows": len(processed_df),
            "rows_filtered": len(original_df) - len(processed_df),
            "columns": len(processed_df.columns),
            "feedback_columns": self.data_processing_config.feedback_columns,
            "max_rows_limit": self.data_processing_config.max_rows_to_process,
            "batch_size": self.data_processing_config.batch_size,
        }

    def _get_csv_parameters(self) -> Dict[str, Any]:
        """
        Get CSV reading parameters from configuration.

        Returns:
            Dictionary of parameters to pass to pandas.read_csv()
        """
        config = self.data_processing_config

        # Build parameters dict, excluding None values
        csv_params = {
            "delimiter": config.csv_delimiter,
            "encoding": config.csv_encoding,
            "header": config.csv_header,
            "quotechar": config.csv_quotechar,
            "decimal": config.csv_decimal,
        }

        # Add optional parameters only if they are set
        if config.csv_escapechar is not None:
            csv_params["escapechar"] = config.csv_escapechar

        if config.csv_thousands is not None:
            csv_params["thousands"] = config.csv_thousands

        if config.csv_na_values is not None:
            csv_params["na_values"] = config.csv_na_values

        return csv_params
