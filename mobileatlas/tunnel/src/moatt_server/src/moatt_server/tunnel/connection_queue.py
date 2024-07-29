import asyncio
import collections
import logging
from collections.abc import Awaitable
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
from uuid import UUID

from moatt_types.connect import ConnectRequest, ConnectResponse, ConnectStatus

from .. import config
from .. import models as dbm

LOGGER = logging.getLogger(__name__)

_QUEUES: dict[UUID, "Queue"] = {}


class QueueEntry:
    def __init__(
        self,
        sim: dbm.Sim,
        probe_id: UUID,
        con_req: ConnectRequest,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        immediate: bool = False,
    ):
        self.sim = sim
        self.probe_id = probe_id
        self.con_req = con_req
        self.reader = reader
        self.writer = writer
        self.immediate = immediate


class Queue(asyncio.Queue):
    # overridable methods from asyncio.Queue

    # called at the end of super().__init__
    def _init(self, maxsize):
        self._queue = collections.deque()
        self._last_active: datetime = datetime.now(tz=timezone.utc)
        self._active: int = 0
        self._gc_task = asyncio.create_task(self._gc())

    def _get(self) -> QueueEntry:
        self._acquire()
        try:
            qe = self._queue.popleft()
            return qe
        finally:
            self._release()

    def _put(self, item: QueueEntry):
        self._queue.append(item)

    # end of overridable methods

    # active if currently running a tunnel?
    def last_active(self) -> Optional[datetime]:
        if self._active > 0:
            return None

        return self._last_active

    def _acquire(self) -> None:
        self._active += 1

    def _release(self) -> None:
        assert self._active > 0

        self._active -= 1

        if self._active == 0:
            self._last_active = datetime.now(tz=timezone.utc)

    def _cleanup(self) -> int:
        self._gc_task.cancel()

        num_closed = 0
        try:
            while True:
                writer = self.get_nowait().writer
                try:
                    writer.write(
                        ConnectResponse(ConnectStatus.ProviderTimedOut).encode()
                    )
                except Exception:
                    pass
                writer.close()
                num_closed += 1
        except asyncio.QueueEmpty:
            pass
        return num_closed

    async def _gc(self):
        while True:
            await asyncio.sleep(config.get_config().QUEUE_GC_INTERVAL.total_seconds())

            if len(self._queue) != 0:
                LOGGER.debug("Queue GC starting.")
                size = len(self._queue)
                self._queue = collections.deque(filter(lambda qe: not qe.writer.is_closing(), self._queue))
                if len(self._queue) < size:
                    LOGGER.info(
                        f"Removed {size - len(self._queue)} closed probe connection(s)."
                    )


def queue_gc_coro_factory(timeout: timedelta) -> Callable[[], Awaitable[None]]:
    async def f():
        conns_closed = 0
        qs_removed = 0
        now = datetime.now(tz=timezone.utc)

        LOGGER.debug("Starting removal of old connection requests")

        # copy items to prevent changing the dict while iterating
        items = list(_QUEUES.items())
        for id, q in items:
            last_active = q.last_active()
            if last_active is not None and now - last_active > timeout:
                del _QUEUES[id]
                qs_removed += 1
                conns_closed += q._cleanup()

        LOGGER.debug(
            "Finished removal of old connection requests. "
            f"(Removed {qs_removed} queues; closed {conns_closed} connections)"
        )

    return f


def _get_queue(id: UUID) -> Queue:
    q = _QUEUES.get(id)
    if q is None:
        q = Queue(maxsize=config.get_config().MAX_QUEUE_SIZE)
        _QUEUES[id] = q
    return q


def put_nowait(id: UUID, qe: QueueEntry) -> None:
    q = _get_queue(id)
    if qe.immediate and len(q._queue) >= len(q._getters):  # type: ignore
        raise asyncio.QueueFull(qe)
    try:
        q.put_nowait(qe)
    except asyncio.QueueFull as e:
        e.args = (qe,)
        raise


async def get(id: UUID) -> QueueEntry:
    q = _get_queue(id)
    return await q.get()


def task_done(id: UUID):
    q = _get_queue(id)
    q.task_done()
