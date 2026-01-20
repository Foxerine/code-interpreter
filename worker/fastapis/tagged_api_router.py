"""
TaggedAPIRouter implementation for automatic tag concatenation.
"""
from enum import Enum
from typing import Sequence

from fastapi import APIRouter, Depends


class TaggedAPIRouter(APIRouter):
    """APIRouter with automatic tag concatenation for API documentation."""

    def __init__(
            self,
            *,
            prefix: str = '',
            tags: list[str | Enum] | None = None,
            tag: str | None = None,
            dependencies: Sequence[Depends] | None = None,
            **kwargs,
    ) -> None:
        if tag is not None:
            self._tag_segment: str = f"/{tag}" if not tag.startswith("/") else tag
        else:
            self._tag_segment = prefix

        self._full_tag: str = self._tag_segment

        if tags is None and self._tag_segment:
            tags = [self._tag_segment]

        super().__init__(
            prefix=prefix,
            tags=tags,
            dependencies=dependencies,
            **kwargs,
        )

    def include_router(
            self,
            router: "APIRouter",
            **kwargs,
    ) -> None:
        if isinstance(router, TaggedAPIRouter) and hasattr(router, '_tag_segment'):
            router._full_tag = self._full_tag + router._tag_segment
            if router.tags:
                router.tags = [router._full_tag]

        super().include_router(router, **kwargs)
