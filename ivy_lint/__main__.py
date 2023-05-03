"""Linting checker and formatter for ivy coding and docstring styles."""

import sys
import argparse

from .formatters import IvyArrayDocstringFormatter

FORMATTERS = (IvyArrayDocstringFormatter,)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="ivy-lint",
        description=__doc__,
    )

    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        metavar="n",
        default=0,
        help="number of parallel jobs; " "match CPU count if value is 0 (default: 0)",
    )
    parser.add_argument(
        "filenames",
        nargs="+",
        help="filenames to check",
    )

    return parser.parse_args()


def main():
    """Entrypoint of ivy-lint."""
    args = parse_args()

    filenames = list(set(args.filenames))

    # TODO divide filenames into chunks and run in parallel
    for formatter in FORMATTERS:
        formatter(filenames).format()


if __name__ == "__main__":
    sys.exit(main())
