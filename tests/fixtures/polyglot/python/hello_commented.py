#!/usr/bin/env python3
# Hello World in Python
# A simple greeting program

import sys  # for sys.exit


def greet(name):
    """Print a greeting to stdout."""
    # Format the message
    print(f"Hello, {name}!")  # output the greeting


def main():
    # Call greet with the classic name
    greet("World")
    return 0  # success


if __name__ == "__main__":
    # Run main when executed directly
    sys.exit(main())
