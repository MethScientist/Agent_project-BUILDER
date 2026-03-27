"""
py_app/main.py

Entry point for the py_app package.
"""

from py_app.utils.math_utils import add, Greeter


def main() -> None:
    """Run a simple demo using the utility functions."""
    sum_result = add(2, 3)
    greeting = Greeter("Hope").greet()
    print(sum_result)
    print(greeting)


if __name__ == "__main__":
    main()
# BEGIN def main
"""
py_app/main.py

Entry point for the py_app package.
"""

from py_app.utils.math_utils import add, Greeter


def main() -> None:
    """Run a simple demo using the utility functions."""
    sum_result = add(2, 3)
    greeting = Greeter("Hope").greet()
    print(sum_result)
    print(greeting)


if __name__ == "__main__":
    main()
# END def main
