from __future__ import annotations

"""CLI entrypoint for nomadcastd per README daemon description."""

import argparse
import logging
import sys
from pathlib import Path

from nomadcastd.config import load_config, load_subscriptions, add_subscription_uri, remove_subscription_uri
from nomadcastd.parsing import normalize_subscription_input
from nomadcastd.daemon import NomadCastDaemon
from nomadcastd.server import NomadCastHTTPServer, NomadCastRequestHandler


def _list_feeds(config_path: Path | None) -> int:
    config = load_config(config_path=config_path)
    subscriptions = load_subscriptions(config.config_path)
    if not subscriptions:
        print("No feeds configured.")
        return 0
    for uri in subscriptions:
        print(uri)
    return 0


def _remove_feed(locator: str, config_path: Path | None) -> int:
    config = load_config(config_path=config_path)
    try:
        uri = normalize_subscription_input(locator)
    except ValueError as exc:
        print(f"Invalid locator: {exc}")
        return 1
    removed = remove_subscription_uri(config.config_path, uri)
    if not removed:
        print("Feed not found.")
        return 1
    print(f"Removed {uri}.")
    return 0


def _add_feed(locator: str, config_path: Path | None) -> int:
    config = load_config(config_path=config_path)
    try:
        uri = normalize_subscription_input(locator)
    except ValueError as exc:
        print(f"Invalid locator: {exc}")
        return 1
    added = add_subscription_uri(config.config_path, uri)
    if not added:
        print("Feed already exists.")
        return 1
    print(f"Added {uri}.")
    return 0


def _run_daemon(config_path: Path | None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config(config_path=config_path)
    daemon = NomadCastDaemon(config=config)
    daemon.start()

    if config.listen_host not in {"127.0.0.1", "localhost"}:
        logging.getLogger("nomadcastd").warning(
            "Binding to non-localhost address %s:%s exposes your feed server.",
            config.listen_host,
            config.listen_port,
        )

    server = NomadCastHTTPServer((config.listen_host, config.listen_port), NomadCastRequestHandler)
    server.daemon = daemon
    logging.getLogger("nomadcastd").info(
        "NomadCast daemon listening on http://%s:%s", config.listen_host, config.listen_port
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        daemon.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the NomadCast daemon HTTP server."""
    parser = argparse.ArgumentParser(description="NomadCast daemon")
    parser.add_argument("--config", help="Override config path")
    subparsers = parser.add_subparsers(dest="command")

    feeds_parser = subparsers.add_parser("feeds", help="Manage feed subscriptions")
    feeds_sub = feeds_parser.add_subparsers(dest="feeds_command")

    feeds_sub.add_parser("ls", help="List configured feeds")
    add_parser = feeds_sub.add_parser("add", help="Add a feed subscription")
    add_parser.add_argument("locator", help="NomadCast locator or destination_hash:ShowName")
    rm_parser = feeds_sub.add_parser("rm", help="Remove a feed subscription")
    rm_parser.add_argument("locator", help="NomadCast locator or destination_hash:ShowName")

    args = parser.parse_args(argv)
    config_path = Path(args.config) if args.config else None

    if args.command == "feeds":
        if args.feeds_command == "ls":
            return _list_feeds(config_path)
        if args.feeds_command == "add":
            return _add_feed(args.locator, config_path)
        if args.feeds_command == "rm":
            return _remove_feed(args.locator, config_path)
        feeds_parser.print_help()
        return 1

    return _run_daemon(config_path)


if __name__ == "__main__":
    sys.exit(main())
