from __future__ import annotations

"""Standalone app launcher for the NomadCast sample creator."""

from typing import NoReturn

from nomadcast.ui_tk_helper import TkHelperLauncher


def main() -> NoReturn:
    TkHelperLauncher().launch()


if __name__ == "__main__":
    main()
