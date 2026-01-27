from __future__ import annotations

"""Standalone app launcher for the NomadCast sample creator."""

from typing import NoReturn

from nomadcast_sample.sample_creator import main as sample_creator_main


def main() -> NoReturn:
    sample_creator_main()


if __name__ == "__main__":
    main()
