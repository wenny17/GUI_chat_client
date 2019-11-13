from contextlib import asynccontextmanager
import asyncio
import socket

import aionursery

RECONNECT_DELAY = 3
CONN_ATTEMPTS_BEFORE_DELAY = 3

async def connect(
                  host, port,
                  status_queue,
                  conn_mode
                  ):
    connection_attempts = 0
    while True:
        try:
            status_queue.put_nowait(conn_mode.INITIATED)

            reader, writer = await asyncio.open_connection(host, port)

            status_queue.put_nowait(conn_mode.ESTABLISHED)
            return reader, writer
        except (
                socket.gaierror,
                ConnectionRefusedError,
                ConnectionResetError
                ):
            status_queue.put_nowait(conn_mode.CLOSED)
            connection_attempts += 1
            if connection_attempts > CONN_ATTEMPTS_BEFORE_DELAY:
                status_queue.put_nowait(conn_mode.INITIATED)
                await asyncio.sleep(RECONNECT_DELAY)


@asynccontextmanager
async def connect_to_addr(
                          host, port,
                          status_queue=None,
                          conn_mode=None
                          ):
    reader, writer = None, None
    try:
        reader, writer = await connect(host, port, status_queue, conn_mode)
        yield reader, writer

    finally:
        if writer:
            writer.close()
            await writer.wait_closed()


@asynccontextmanager
async def create_handy_nursery():
    try:
        async with aionursery.Nursery() as nursery:
            yield nursery
    except aionursery.MultiError as e:
        if len(e.exceptions) == 1:
            raise e.exceptions[0] from None
        raise



