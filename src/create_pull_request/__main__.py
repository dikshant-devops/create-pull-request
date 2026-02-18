"""
Entry point for create-pull-request action.

Allows the package to be executed as a module:
    python -m create_pull_request
"""

from .main import run

if __name__ == "__main__":
    run()
