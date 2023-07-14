# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

import argparse
import asyncio
import logging
import os
import pickle
import ssl
import time
from collections import deque
from typing import AsyncIterator, Deque, Dict, Optional, Tuple, cast
from urllib.parse import urlparse

import httpcore
from httpx import AsyncClient, Response

from aioquic.asyncio.client import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import DataReceived, H3Event, Headers, HeadersReceived
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent


logger = logging.getLogger(__name__)


class H3Transport(QuicConnectionProtocol, httpcore.AsyncHTTPTransport):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._http = H3Connection(self._quic)
        self._read_queue: Dict[int, Deque[H3Event]] = {}
        self._read_ready: Dict[int, asyncio.Event] = {}

    async def handle_async_request(
        self,
        method: bytes,
        url: Tuple[bytes, bytes, Optional[int], bytes],
        headers: Headers = None,
        stream: httpcore.AsyncByteStream = None,
        extensions: dict = None,
    ) -> Tuple[int, Headers, httpcore.AsyncByteStream, dict]:
        stream_id = self._quic.get_next_available_stream_id()
        self._read_queue[stream_id] = deque()
        self._read_ready[stream_id] = asyncio.Event()
        # prepare request
        self._http.send_headers(
            stream_id=stream_id,
            headers=[
                (b":method", method),
                (b":scheme", url[0]),
                (b":authority", url[1]),
                (b":path", url[3]),
            ]
            + [
                (k.lower(), v)
                for (k, v) in headers
                if k.lower() not in (b"connection", b"host")
            ],
        )
        async for data in stream:
            self._http.send_data(stream_id=stream_id, data=data, end_stream=False)
        self._http.send_data(stream_id=stream_id, data=b"", end_stream=True)

        # transmit request
        self.transmit()

        # process response
        status_code, headers, stream_ended = await self._receive_response(stream_id)
        response_stream = httpcore.AsyncIteratorByteStream(
            aiterator=self._receive_response_data(stream_id, stream_ended)
        )

        return (
            status_code,
            headers,
            response_stream,
            {
                "http_version": b"HTTP/3",
            },
        )

    def http_event_received(self, event: H3Event):
        if isinstance(event, (HeadersReceived, DataReceived)):
            stream_id = event.stream_id
            if stream_id in self._read_queue:
                self._read_queue[event.stream_id].append(event)
                self._read_ready[event.stream_id].set()

    def quic_event_received(self, event: QuicEvent):
        #  pass event to the HTTP layer
        if self._http is not None:
            for http_event in self._http.handle_event(event):
                self.http_event_received(http_event)

    async def _receive_response(self, stream_id: int) -> Tuple[int, Headers, bool]:
        """
        Read the response status and headers.
        """
        
        stream_ended = False
        while True:
            event = await self._wait_for_http_event(stream_id)
            if isinstance(event, HeadersReceived):
                stream_ended = event.stream_ended
                break

        headers = []
        status_code = 0
        for header, value in event.headers:
            if header == b":status":
                status_code = int(value.decode())
            else:
                headers.append((header, value))
        return status_code, headers, stream_ended

    async def _receive_response_data(
        self, stream_id: int, stream_ended: bool
    ) -> AsyncIterator[bytes]:
        """
        Read the response data.
        """
        while not stream_ended:
            event = await self._wait_for_http_event(stream_id)
            if isinstance(event, DataReceived):
                stream_ended = event.stream_ended
                yield event.data
            elif isinstance(event, HeadersReceived):
                stream_ended = event.stream_ended

    async def _wait_for_http_event(self, stream_id: int) -> H3Event:
        """
        Returns the next HTTP/3 event for the given stream.
        """
        if not self._read_queue[stream_id]:
            await self._read_ready[stream_id].wait()
        event = self._read_queue[stream_id].popleft()
        if not self._read_queue[stream_id]:
            self._read_ready[stream_id].clear()
        return event


def save_session_ticket(ticket):
    """
    Callback which is invoked by the TLS engine when a new session ticket
    is received.
    """
    logger.info("New session ticket received")
    #if args.session_ticket:
    #    with open(args.session_ticket, "wb") as fp:
    #        pickle.dump(ticket, fp)


async def run(
    configuration: QuicConfiguration,
    url: str,
    data: str,
) -> None:
    # parse URL
    parsed = urlparse(url)
    assert parsed.scheme == "https", "Only https:// URLs are supported."
    host = parsed.hostname
    if parsed.port is not None:
        port = parsed.port
    else:
        port = 443

    async with connect(
        host,
        port,
        configuration=configuration,
        create_protocol=H3Transport,
        session_ticket_handler=save_session_ticket,
    ) as transport:
        async with AsyncClient(
            transport=cast(httpcore.AsyncHTTPTransport, transport)
        ) as client:
            # perform request
            start = time.time()
            if data is not None:
                response = await client.post(
                    url,
                    content=data.encode(),
                    headers={"content-type": "application/x-www-form-urlencoded"},
                )
            else:
                response = await client.get(url)

            elapsed = time.time() - start

        # print speed
        octets = len(response.content)
        logger.info(
            "Received %d bytes in %.1f s (%.3f Mbps)"
            % (octets, elapsed, octets * 8 / elapsed / 1000000)
        )

        ## output response
        #if output_dir is not None:
        #    output_path = os.path.join(
        #        output_dir, os.path.basename(urlparse(url).path) or "index.html"
        #    )
        #    with open(output_path, "wb") as output_file:
        #        if include:
        #            headers = ""
        #            for header, value in response.headers.items():
        #                headers += header + ": " + value + "\r\n"
        #            if headers:
        #                output_file.write(headers.encode() + b"\r\n")
        #        output_file.write(response.content)
        return response

class QuicWrapper():
    def __init__(self):
        logger.setLevel(logging.DEBUG)
        # prepare configuration
        self.configuration = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN)

        #disable cert checking:
        self.configuration.verify_mode = ssl.CERT_NONE
    
    def request(self, url, data = None, timeout=90) -> Response:
        loop = asyncio.get_event_loop()
        r = loop.run_until_complete(
            asyncio.wait_for(
                run(
                    configuration=self.configuration,
                    url=url,
                    data=data
                ),
                timeout
            )
        )
        #print(r.content)
        return r

if __name__ == "__main__":
    quic = QuicWrapper()
    r = quic.request("https://quic.aiortc.org/1")
    print(r)
