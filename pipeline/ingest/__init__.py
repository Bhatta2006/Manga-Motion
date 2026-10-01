"""CPU-only chapter import; original image files are never re-encoded."""


class ImportFailure(ValueError):
    """A named source/page failed validation; the last complete manifest stays valid."""

