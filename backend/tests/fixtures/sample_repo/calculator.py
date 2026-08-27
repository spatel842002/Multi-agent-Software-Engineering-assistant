"""A tiny calculator module used as a fixture repository in ingestion tests."""


def add(a: int, b: int) -> int:
    """Returns the sum of a and b."""
    return a + b


def divide(a: int, b: int) -> float:
    """Returns a divided by b.

    Raises ZeroDivisionError if b is zero -- this is intentional, not a bug,
    but is useful as a fixture for the bug-investigation workflow's tests.
    """
    return a / b


class Calculator:
    """Accumulates a running total across operations."""

    def __init__(self) -> None:
        self.total = 0

    def add(self, value: int) -> int:
        self.total += value
        return self.total

    def reset(self) -> None:
        self.total = 0
