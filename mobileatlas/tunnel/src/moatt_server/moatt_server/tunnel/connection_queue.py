import asyncio

queues = {}

def _get_queue(session_token) -> asyncio.Queue:
    q = queues.get(session_token)
    if q == None:
        q = asyncio.Queue()
        queues[session_token] = q
    return q

async def put(session_token, x):
    q = _get_queue(session_token)
    await q.put(x)

async def get(session_token):
    q = _get_queue(session_token)
    return await q.get()
