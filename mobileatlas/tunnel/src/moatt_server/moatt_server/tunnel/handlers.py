import logging

from moatt_types.connect import AuthStatus, ConnectStatus

# TODO:
# * timeouts

logger = logging.getLogger(__name__)

class SimRequestError(Exception):
    def __init__(self, ident, status: ConnectStatus):
        self.ident = ident
        self.status = status
        super().__init__(f"Requesting SIM ({ident}) failed with {status}")

class AuthorisationError(Exception):
    def __init__(self, status: AuthStatus):
        self.status = status
        super().__init__(f"Authorisation failed with {status}")

def auto_close(f):
    async def wrapped(reader, writer):
        try:
            await f(reader, writer)
        finally:
            writer.close()
            await writer.wait_closed()
    return wrapped

#async def main():
#    async with asyncio.TaskGroup() as tg:
#        tg.create_task(asyncio.start_server(handle_probe, '::', 5555))
#        tg.create_task(asyncio.start_server(handle_provider, '::', 6666))

#@auto_close
#async def handle_probe(reader, writer):
#    read = await reader.read(n=2048)
#
#    # TODO: handle connection request longer than 2048 bytes
#    if len(read) == 0 or len(read) == 2048:
#        return
#
#    cr = ConnectionRequest.decode(read)
#
#    if cr == None:
#        return
#    
#    auth(cr)
