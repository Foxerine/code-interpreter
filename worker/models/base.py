"""
Base model for all Worker models.
"""
from pydantic import BaseModel, ConfigDict


class ModelBase(BaseModel):
    model_config = ConfigDict(
        use_attribute_docstrings=True,
        validate_by_name=True,
        extra='forbid',
    )
