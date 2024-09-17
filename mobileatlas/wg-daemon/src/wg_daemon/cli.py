import asyncio
import logging
import sys

import uvicorn
from systemd.daemon import listen_fds

from .config import Settings
from .routes import app

LOGGER = logging.getLogger(__name__)


def main():
    # initialize Settings
    Settings.get()

    fds = listen_fds()

    if len(fds) == 0:
        LOGGER.error("Did not receive an fd from systemd.")
        sys.exit(1)
    elif len(fds) > 1:
        LOGGER.error(
            "Received multiple fds from systemd. wg-daemon can only handle one."
        )
        sys.exit(1)

    config = uvicorn.Config(app, fd=fds[0])
    server = uvicorn.Server(config)

    asyncio.run(run_server(server))


async def run_server(server: uvicorn.Server):
    server_task = asyncio.create_task(server.serve())
    should_exit = False

    while True:
        requests = server.server_state.total_requests

        done, _ = await asyncio.wait([server_task], timeout=10 * 60)

        if server_task in done:
            break
        elif should_exit:
            LOGGER.error("Server did not stop after 10mins. Canceling task...")
            server_task.cancel()
            break

        if requests == server.server_state.total_requests:
            LOGGER.info("Server has been idling for more than 10mins. Shutting down...")
            should_exit = True
            server.should_exit = True


if __name__ == "__main__":
    main()
