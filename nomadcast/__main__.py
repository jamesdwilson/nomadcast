from __future__ import annotations

"""CLI entrypoint for the NomadCast v0 UI."""

import argparse
import sys
from typing import NoReturn

from nomadcast.protocol_handler import ensure_protocol_handler_registered
from nomadcast.ui import SubscriptionService
from nomadcast.ui_tk_helper import TkHelperLauncher


def _run_protocol_handler(locator: str) -> int:
    """Handle protocol handler invocations with a locator argument."""
    service = SubscriptionService()
    try:
        status = service.add_subscription(locator)
    except ValueError as exc:
        print(f"Invalid locator: {exc}")
        return 1
    except OSError as exc:
        print(f"Failed to update config: {exc}")
        return 1

    print(status.message)
    return 0


def main() -> NoReturn:
    ensure_protocol_handler_registered()
    parser = argparse.ArgumentParser(description="NomadCast v0 UI")
    parser.add_argument("locator", nargs="?", help="NomadCast locator to subscribe")
    args = parser.parse_args()

    if args.locator:
        sys.exit(_run_protocol_handler(args.locator))

    TkHelperLauncher().launch()


if __name__ == "__main__":
    main()
