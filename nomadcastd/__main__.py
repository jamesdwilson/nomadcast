from __future__ import annotations

"""CLI entrypoint for nomadcastd per README daemon description."""

import argparse
import logging
import sys
from pathlib import Path

from nomadcastd.config import load_config
from nomadcastd.daemon import NomadCastDaemon
from nomadcastd.server import NomadCastHTTPServer, NomadCastRequestHandler


def main(argv: list[str] | None = None) -> int:
    """Run the NomadCast daemon HTTP server."""
    parser = argparse.ArgumentParser(description="NomadCast daemon")
    parser.add_argument("--config", help="Override config path")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config(config_path=Path(args.config) if args.config else None)
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


if __name__ == "__main__":
    sys.exit(main())
