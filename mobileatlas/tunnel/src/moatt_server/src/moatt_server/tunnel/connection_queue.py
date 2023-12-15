import asyncio
import collections
import logging
import time
from collections.abc import Awaitable
from typing import Callable, Optional

from moatt_types.connect import ConnectRequest, ConnectResponse, ConnectStatus

from .. import config
from .. import models as dbm

logger = logging.getLogger(__name__)

queues: dict[int, "Queue"] = {}


class QueueEntry:
    def __init__(
        self,
        sim: dbm.Sim,
        con_req: ConnectRequest,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        self.sim = sim
        self.con_req = con_req
        self.reader = reader
        self.writer = writer
        # self.liveness_check_task = liveness_check_task


class Queue(asyncio.Queue):
    # overridable methods from asyncio.Queue

    # called at the end of super().__init__
    def _init(self, _):
        self._queue = collections.deque()
        self._last_active: int = time.monotonic_ns()
        self._active: int = 0
        self._gc_task = asyncio.create_task(self._gc())

    def _get(self) -> QueueEntry:
        self._acquire()
        try:
            return self._queue.popleft()
        finally:
            self._release()

    def _put(self, qe: QueueEntry):
        self._queue.append(qe)

    # end of overridable methods

    # active if currently running a tunnel?
    def last_active(self) -> Optional[int]:
        if self._active > 0:
            return None

        return self._last_active

    def _acquire(self) -> None:
        self._active += 1

    def _release(self) -> None:
        assert self._active > 0

        self._active -= 1

        if self._active == 0:
            self._last_active = time.monotonic_ns()

    async def _cleanup(self) -> int:
        self._gc_task.cancel()

        num_closed = 0
        try:
            while True:
                writer = self.get_nowait().writer
                try:
                    writer.write(
                        ConnectResponse(ConnectStatus.ProviderTimedOut).encode()
                    )
                except:
                    pass
                writer.close()
                await writer.wait_closed()
                num_closed += 1
        except asyncio.QueueEmpty:
            pass
        return num_closed

    async def _gc(self):
        def f(qe):
            if qe.writer.is_closing():
                return False
            else:
                return True

        while True:
            await asyncio.sleep(config.QUEUE_GC_INTERVAL)

            if len(self._queue) != 0:
                logger.debug("queue GC")  # TODO
                size = len(self._queue)
                self._queue = collections.deque(filter(lambda x: f(x), self._queue))
                if len(self._queue) < size:
                    logger.info(
                        f"Removed {size - len(self._queue)} closed probe connection(s)."
                    )


# TODO: update db
def queue_gc_coro_factory(timeout) -> Callable[[], Awaitable[None]]:
    async def f():
        conns_closed = 0
        qs_removed = 0
        now = time.monotonic_ns()
        timeout_ns = timeout * 10**9

        logger.info(f"Starting removal of old connection requests")

        # TODO: test whether list is needed
        for id, q in list(queues.items()):
            last_active = q.last_active()
            if last_active is not None and now - last_active > timeout_ns:
                del queues[id]
                qs_removed += 1
                conns_closed += await q._cleanup()

        logger.info(
            f"Finished removal of old connection requests. (Removed {qs_removed} queues; closed {conns_closed} connections)"
        )

    return f


def _get_queue(id: int) -> Queue:
    q = queues.get(id)
    if q is None:
        q = Queue()
        queues[id] = q
    return q


async def put(id: int, qe: QueueEntry) -> None:
    q = _get_queue(id)
    await q.put(qe)


async def get(id: int) -> QueueEntry:
    q = _get_queue(id)
    return await q.get()


def task_done(id: int):
    q = _get_queue(id)
    q.task_done()
