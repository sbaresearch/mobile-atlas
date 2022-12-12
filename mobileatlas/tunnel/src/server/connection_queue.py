import asyncio

queues = {}

def _get_queue(provider_id) -> asyncio.Queue:
    q = queues.get(provider_id)
    if q == None:
        q = asyncio.Queue()
        queues[provider_id] = q
    return q

async def put(provider_id, x):
    q = _get_queue(provider_id)
    await q.put(x)

async def get(provider_id):
    q = _get_queue(provider_id)
    return await q.get()
