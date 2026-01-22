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
        # Pattern breakdown:
        # ^/sandbox - must start with /sandbox
        # (/[\w\-]+(\.[\w\-]+)*)* - path segments: alphanumeric with optional .extension
        # /?$ - optional trailing slash
        # This prevents '..' by not allowing consecutive dots or dots at segment boundaries
        pattern=r'^/sandbox(/[\w\-]+(\.[\w\-]+)*)*/?$'
    )
]
"""
Path within sandbox directory.
Must start with /sandbox, path segments contain alphanumeric/dash/underscore,
with optional file extensions (e.g., .txt). Prevents path traversal (.. is blocked).
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
