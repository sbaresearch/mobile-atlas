import argparse
import logging
from pathlib import Path

import uvicorn
import uvloop

from .config import init_config
from .main import app

LOGGER = logging.getLogger(__name__)

LOG_LEVELS = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    parser.add_argument(
        "-l",
        "--loglevel",
        type=str.lower,
        choices=LOG_LEVELS.keys(),
        default="info",
        help="Set the log level",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Set host of the HTTP server",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8000,
        help="Set port of the HTTP server",
    )
    parser.add_argument(
        "--root-path",
        type=str,
        default="",
        help="Set root path of the HTTP server",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=Path("config.toml"),
        help="Path to configuration file.",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=LOG_LEVELS[args.loglevel])

    cfg = init_config(args.config, SERVER_HOST=args.host, SERVER_PORT=args.port)

    server_cfg = uvicorn.Config(
        app, host=args.host, port=cfg.SERVER_PORT, root_path=args.root_path
    )
    server = uvicorn.Server(server_cfg)
    uvloop.run(server.serve())


if __name__ == "__main__":
    main()
