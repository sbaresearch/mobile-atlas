import logging
import sys

import uvicorn
from systemd.daemon import listen_fds

from .config import Settings
from .routes import app

LOGGER = logging.getLogger(__name__)


def main():
    settings = Settings.get()

    fds = listen_fds()

    if len(fds) == 0:
        LOGGER.error("Did not receive an fd from systemd.")
        sys.exit(1)
    elif len(fds) > 1:
        LOGGER.error(
            "Received multiple fds from systemd. wg-daemon can only handle one."
        )
        sys.exit(1)

    uvicorn.run(app, fd=fds[0])


if __name__ == "__main__":
    main()
