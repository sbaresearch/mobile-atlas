import argparse
import logging
import logging.config
import ssl

import uvloop

from .. import config
from .server import Server

LOGGER = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--host", default="127.0.0.1", nargs="*")
    parser.add_argument("--port", "-p", type=int)
    parser.add_argument("--cert", default="ssl/server.crt")
    parser.add_argument("--cert-key", default="ssl/server.key")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--allow-auth-plugins", action="store_true")
    args = parser.parse_args()

    config.init_config(args.config, args.allow_auth_plugins, args)

    log_conf = config.get_config().LOGGING_CONF_FILE
    if log_conf is not None:
        logging.config.fileConfig(log_conf)

    tls_ctx = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    tls_ctx.verify_mode = ssl.CERT_REQUIRED
    tls_ctx.load_cert_chain(args.cert, args.cert_key)

    server = Server(config.get_config(), args.host, args.port, tls_ctx)

    uvloop.run(server.start())


if __name__ == "__main__":
    main()
