"""
Common type aliases for the gateway.

This module provides reusable type aliases with validation constraints.
Following foxline conventions, uses Field() for all constraints.
"""
from typing import Annotated, TypeAlias

from pydantic import Field


# =============================================================================
# String Length Constraints
# =============================================================================

Str32: TypeAlias = Annotated[str, Field(max_length=32)]
Str64: TypeAlias = Annotated[str, Field(max_length=64)]
Str128: TypeAlias = Annotated[str, Field(max_length=128)]
Str256: TypeAlias = Annotated[str, Field(max_length=256)]
Str1024: TypeAlias = Annotated[str, Field(max_length=1024)]
Str1280: TypeAlias = Annotated[str, Field(max_length=1280)]


# =============================================================================
# Numeric Constraints
# =============================================================================

NonNegativeInt: TypeAlias = Annotated[int, Field(ge=0)]
PositiveInt: TypeAlias = Annotated[int, Field(ge=1)]


# =============================================================================
# Sandbox Path Constraints
# =============================================================================

SandboxPathStr: TypeAlias = Annotated[
    str,
    Field(
        min_length=1,
        max_length=1024,
        pattern=r'^/sandbox(/[\w\-\.]+)*/?$'
    )
]
"""
Path within sandbox directory.
Must start with /sandbox and contain only alphanumeric, dash, underscore, dot.
"""

SandboxFileName: TypeAlias = Annotated[
    str,
    Field(
        min_length=1,
        max_length=255,
        pattern=r'^[\w\-\.]+$'
    )
]
"""
Filename for sandbox files.
Only alphanumeric, dash, underscore, dot allowed.
"""
