"""
Base classes for models.

This module provides base classes for consistent model design.
"""
from pydantic import BaseModel, ConfigDict


class ModelBase(BaseModel):
    """
    Base class for all models in the gateway.

    Features:
    - use_attribute_docstrings: Uses field docstrings for schema descriptions
    - validate_by_name: Allows validation by field name
    - extra='forbid': Rejects unknown fields in requests
    """
    model_config = ConfigDict(
        use_attribute_docstrings=True,
        validate_by_name=True,
        extra='forbid',
    )
