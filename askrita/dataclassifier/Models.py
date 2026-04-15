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
#   pydantic (MIT)

"""Dynamic Pydantic model generation for data classification structured output."""

import logging
from typing import Any, Dict, Literal, Optional, Type

from pydantic import BaseModel, Field, create_model

logger = logging.getLogger(__name__)


def _resolve_field_annotation(
    field_name: str, field_type: str, field_config: Dict[str, Any], default_value: Any
) -> tuple:
    """Resolve the Pydantic field annotation and default for a given type string.

    Returns (field_annotation, default_value).
    """
    if field_type == "literal":
        values = field_config.get("values", [])
        if not values:
            logger.warning(
                f"No values provided for literal field '{field_name}', using string instead"
            )
            return str, default_value
        return Literal[tuple(values)], default_value
    if field_type == "string":
        return str, default_value
    if field_type == "optional_string":
        return Optional[str], (None if default_value == ... else default_value)
    if field_type == "list":
        item_type = field_config.get("item_type", "string")
        annotation = Optional[list[str]] if item_type == "string" else Optional[list]
        return annotation, (None if default_value == ... else default_value)
    if field_type == "integer":
        return int, default_value
    if field_type == "float":
        return float, default_value
    logger.warning(
        f"Unknown field type '{field_type}' for field '{field_name}', using string"
    )
    return str, default_value


def create_dynamic_classification_model(
    field_definitions: Dict[str, Dict[str, Any]],
    model_name: str = "DynamicClassificationModel",
) -> Type[BaseModel]:
    """
    Dynamically create a Pydantic model based on field definitions from configuration.

    Args:
        field_definitions: Dictionary defining fields and their types/constraints
        model_name: Name for the generated model class

    Returns:
        Dynamically created Pydantic model class

    Example field_definitions:
    {
        "sentiment": {
            "type": "literal",
            "values": ["Positive", "Negative", "Neutral"],
            "description": "Sentiment of the text"
        },
        "category": {
            "type": "string",
            "description": "Category classification"
        },
        "confidence": {
            "type": "literal",
            "values": ["Low", "Medium", "High"],
            "default": "Medium",
            "description": "Confidence level"
        }
    }
    """
    logger.info(
        f"Creating dynamic model '{model_name}' with {len(field_definitions)} fields"
    )

    fields = {}

    for field_name, field_config in field_definitions.items():
        field_type = field_config.get("type", "string")
        description = field_config.get("description", f"Field: {field_name}")
        default_value = field_config.get("default", ...)
        required = default_value == ...

        try:
            field_annotation, default_value = _resolve_field_annotation(
                field_name, field_type, field_config, default_value
            )

            # Create Field with proper configuration
            if required:
                field_instance = Field(..., description=description)
            else:
                field_instance = Field(default=default_value, description=description)

            fields[field_name] = (field_annotation, field_instance)

            logger.debug(
                f"Added field '{field_name}': {field_annotation} = {field_instance}"
            )

        except Exception as e:
            logger.error(f"Failed to create field '{field_name}': {e}")
            # Fallback to string field
            fields[field_name] = (str, Field(..., description=description))

    if not fields:
        logger.warning("No valid fields defined, creating empty model")
        fields["placeholder"] = (str, Field("", description="Placeholder field"))

    # Create the dynamic model
    try:
        dynamic_model = create_model(model_name, **fields)
        logger.info(
            f"Successfully created dynamic model '{model_name}' with fields: {list(fields.keys())}"
        )
        return dynamic_model

    except Exception as e:
        logger.error(f"Failed to create dynamic model '{model_name}': {e}")
        # Return a basic fallback model
        return create_basic_fallback_model(model_name)


def create_basic_fallback_model(model_name: str = "FallbackModel") -> Type[BaseModel]:
    """Create a basic fallback model when dynamic creation fails."""

    class FallbackModel(BaseModel):
        """Fallback model when dynamic creation fails."""

        result: str = Field("", description="Classification result")
        category: str = Field("Other", description="Category classification")

    FallbackModel.__name__ = model_name
    logger.warning(f"Using fallback model '{model_name}' due to configuration errors")
    return FallbackModel
