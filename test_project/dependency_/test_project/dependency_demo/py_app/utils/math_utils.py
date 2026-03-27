def add(a, b):
    """Return the sum of a and b."""
    return a + b


class Greeter:
    """Simple greeter that returns a greeting for a given name."""

    def __init__(self, name):
        self.name = name

    def greet(self):
        """Return a greeting string."""
        return f"Hello, {self.name}"