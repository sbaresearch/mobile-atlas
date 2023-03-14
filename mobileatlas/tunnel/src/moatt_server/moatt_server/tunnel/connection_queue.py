import asyncio

queues = {}

def _get_queue(session_token) -> asyncio.Queue:
    q = queues.get(session_token)
    if q == None:
        q = asyncio.Queue()
        queues[session_token] = q
    return q

async def put(id: int, x):
    q = _get_queue(id)
    await q.put(x)

async def get(id: int):
    q = _get_queue(id)
    return await q.get()
