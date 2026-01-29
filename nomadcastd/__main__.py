from __future__ import annotations

"""CLI entrypoint for nomadcastd per README daemon description."""

import argparse
import errno
import logging
import socket
import sys
from pathlib import Path
from dataclasses import replace

from nomadcastd.config import (
    add_no_mirror_uri,
    add_subscription_uri,
    load_config,
    load_subscriptions,
    remove_subscription_uri,
)
from nomadcastd.parsing import encode_show_path, normalize_subscription_input, parse_subscription_uri
from nomadcastd.daemon import NomadCastDaemon
from nomadcastd.server import NomadCastHTTPServer, NomadCastRequestHandler


def _local_feed_base_url(config) -> str:
    host = config.public_host
    if not host:
        host = config.listen_host if config.listen_host != "0.0.0.0" else "127.0.0.1"
    return f"http://{host}:{config.listen_port}"


def _list_feeds(config_path: Path | None) -> int:
    config = load_config(config_path=config_path)
    subscriptions = load_subscriptions(config.config_path)
    if not subscriptions:
        print("No feeds configured.")
        return 0
    base_url = _local_feed_base_url(config)
    for uri in subscriptions:
        try:
            subscription = parse_subscription_uri(uri)
        except ValueError:
            print(uri)
            continue
        show_path = encode_show_path(subscription.destination_hash, subscription.show_name)
        print(f"{uri}\n  local: {base_url}/feeds/{show_path}")
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


def _add_feed(locator: str, config_path: Path | None, *, mirror_enabled: bool) -> int:
    config = load_config(config_path=config_path)
    try:
        uri = normalize_subscription_input(locator)
    except ValueError as exc:
        print(f"Invalid locator: {exc}")
        return 1
    added = add_subscription_uri(config.config_path, uri)
    if not mirror_enabled:
        add_no_mirror_uri(config.config_path, uri)
    if not added:
        print("Feed already exists.")
        return 1
    print(f"Added {uri}.")
    return 0


def _run_daemon(
    config_path: Path | None,
    reticulum_override: Path | None = None,
    *,
    starter_pack_force: bool = False,
    starter_pack_pages_path: Path | None = None,
) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger("nomadcastd")
    config = load_config(config_path=config_path)
    if reticulum_override is not None:
        config = replace(config, reticulum_config_dir=str(reticulum_override))
    daemon = NomadCastDaemon(
        config=config,
        starter_pack_force=starter_pack_force,
        starter_pack_pages_path=starter_pack_pages_path,
    )
    daemon.start()

    logger.info(
        "NomadCast config loaded from %s",
        config.config_path,
    )
    logger.info(
        "Feed server config: listen_host=%s listen_port=%s public_host=%s",
        config.listen_host,
        config.listen_port,
        config.public_host or "(none)",
    )
    if reticulum_override is not None:
        logger.info(
            "Reticulum interface config source: config_dir=%s (from --config directory override)",
            config.reticulum_config_dir,
        )
    else:
        logger.info(
            "Reticulum interface config source: config_dir=%s",
            config.reticulum_config_dir or "(default Reticulum config, e.g. ~/.reticulum)",
        )
    logger.info(
        "Reticulum destination app/aspects: app=%s aspects=%s",
        config.reticulum_destination_app,
        ",".join(config.reticulum_destination_aspects),
    )
    logger.info(
        "To use a different config file (including other interface settings), run: nomadcastd --config PATH"
    )

    if config.reticulum_config_dir is None:
        logger.info("Reticulum config_dir not set; using Reticulum defaults (e.g. ~/.reticulum).")

    if config.listen_host not in {"127.0.0.1", "localhost", "::1"}:
        logger.warning(
            "Binding to non-localhost address %s:%s exposes your feed server.",
            config.listen_host,
            config.listen_port,
        )

    try:
        server = NomadCastHTTPServer((config.listen_host, config.listen_port), NomadCastRequestHandler)
    except OSError as exc:
        logger.error("Failed to bind HTTP server on %s:%s.", config.listen_host, config.listen_port)
        if isinstance(exc, socket.gaierror):
            logger.error(
                "The listen_host %r could not be resolved. Check for blank or commented values in %s; "
                "set listen_host to 127.0.0.1 or localhost, or remove it to use the default.",
                config.listen_host,
                config.config_path,
            )
        elif exc.errno == errno.EADDRINUSE:
            logger.error(
                "Port %s is already in use. Stop the other process or change listen_port in %s.",
                config.listen_port,
                config.config_path,
            )
        elif exc.errno in {errno.EACCES, errno.EPERM}:
            logger.error(
                "Permission denied binding to port %s. Use a port above 1024 or adjust permissions.",
                config.listen_port,
            )
        else:
            logger.error("OS error while binding: %s", exc)
        daemon.stop()
        return 1
    server.daemon = daemon
    logger.info(
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
    parser.add_argument(
        "--starter-pack",
        action="store_true",
        help="Install the starter pack pages now (useful for automation).",
    )
    parser.add_argument(
        "--starter-pack-path",
        help="Override the pages path used for starter pack installation.",
    )
    subparsers = parser.add_subparsers(dest="command")

    feeds_parser = subparsers.add_parser("feeds", help="Manage feed subscriptions")
    feeds_sub = feeds_parser.add_subparsers(dest="feeds_command")

    feeds_sub.add_parser("ls", help="List configured feeds")
    add_parser = feeds_sub.add_parser("add", help="Add a feed subscription")
    add_parser.add_argument("locator", help="NomadCast locator or destination_hash:ShowName")
    add_parser.add_argument(
        "--no-mirror",
        dest="mirror",
        action="store_false",
        help="Do not expose/share via Nomad Network hosting.",
    )
    add_parser.add_argument(
        "--nomirror",
        dest="mirror",
        action="store_false",
        help=argparse.SUPPRESS,
    )
    add_parser.set_defaults(mirror=True)
    rm_parser = feeds_sub.add_parser("rm", help="Remove a feed subscription")
    rm_parser.add_argument("locator", help="NomadCast locator or destination_hash:ShowName")

    args = parser.parse_args(argv)
    config_path = Path(args.config) if args.config else None
    reticulum_override: Path | None = None
    if config_path is not None and config_path.exists() and config_path.is_dir():
        reticulum_override = config_path
        config_path = None

    if args.command == "feeds":
        if args.feeds_command == "ls":
            return _list_feeds(config_path)
        if args.feeds_command == "add":
            return _add_feed(args.locator, config_path, mirror_enabled=args.mirror)
        if args.feeds_command == "rm":
            return _remove_feed(args.locator, config_path)
        feeds_parser.print_help()
        return 1

    starter_pack_pages_path = Path(args.starter_pack_path).expanduser() if args.starter_pack_path else None
    return _run_daemon(
        config_path,
        reticulum_override,
        starter_pack_force=args.starter_pack,
        starter_pack_pages_path=starter_pack_pages_path,
    )


if __name__ == "__main__":
    sys.exit(main())
