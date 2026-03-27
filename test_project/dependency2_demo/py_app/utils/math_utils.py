Here is the corrected **`math_utils.py`** file.  
The `from __future__ import annotations` statement is now placed immediately after the module docstring (as required), and the duplicated code and stray markers have been removed. The logic of the module remains unchanged.

```python
"""Utility functions for the demo application."""

from __future__ import annotations

from typing import Any, Union

# A type that can be any numeric type (int, float, complex) or any other type.
Number = Union[int, float, complex, Any]


def add(a: Number, b: Number) -> Number:
    """Return the sum of *a* and *b*.

    This tiny helper mirrors the behaviour of the built‑in ``+`` operator but
    provides a named entry point for the demo application.
    """
    return a + b


class Greeter:
    """Simple greeter that stores a name and produces a greeting."""

    def __init__(self, name: str):
        self.name = name

    def greet(self) -> str:
        """Return a friendly greeting for the stored name."""
        return f"Hello, {self.name}"


# Exported symbols for `from utils.math_utils import *`
__all__: list[str] = ["add", "Greeter"]
```

This version will import without syntax errors and retains the original functionality.