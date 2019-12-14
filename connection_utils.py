import asyncio
import logging
import json
from tkinter import messagebox
from contextlib import asynccontextmanager
import socket
from typing import AsyncGenerator, Tuple, Union, Dict

import async_timeout
from utils import create_handy_nursery

from exceptions import InvalidToken
from registration_gui import register_draw
from gui import (
    ReadConnectionStateChanged as ReadState,
    SendingConnectionStateChanged as SendState
)

PING_TIMEOUT = 1


logger = logging.getLogger(__name__)
logger.addHandler(logging.FileHandler("logging.log"))
logger.setLevel(logging.INFO)


@asynccontextmanager
async def connect(
        host: str,
        port: int,
        status_queue: asyncio.Queue,
        connect_state_mode: Union[ReadState, SendState],
        timeout: Union[int, float] = 3
) -> AsyncGenerator[Tuple[asyncio.StreamReader, asyncio.StreamWriter], None]:

    await status_queue.put(connect_state_mode.INITIATED)
    try:
        with async_timeout.timeout(timeout):
            reader, writer = await asyncio.open_connection(host, port)
    except (socket.gaierror,
            ConnectionRefusedError,
            ConnectionResetError,
            asyncio.TimeoutError):
        raise ConnectionError
    await status_queue.put(connect_state_mode.ESTABLISHED)
    try:
        yield reader, writer
    finally:
        writer.close()
        await writer.wait_closed()
        await status_queue.put(connect_state_mode.CLOSED)


async def authorise(reader: asyncio.StreamReader,
                    writer: asyncio.StreamWriter,
                    token: str,
                    skip_entry_message: bool=False) -> Dict[str, str]:
    message = await _read_and_log(reader)  # entry_message
    await _write_and_log(writer, token)
    message = await _read_and_log(reader)
    auth_response = json.loads(message)
    if not auth_response:
        logger.debug("Wrong token")
        raise InvalidToken
    user = auth_response["nickname"]
    logger.debug(f"authorization done. User: {user}")
    return user


async def _read_and_log(reader: asyncio.StreamReader) -> str:
    message = (await reader.readline()).decode('utf-8')
    logger.debug("RECEIVE: {}".format(message))
    return message


async def _write_and_log(writer: asyncio.StreamWriter, message: str) -> None:
    writer.write(message.encode() + b'\n')
    logger.debug("SEND: {}".format(message))
    await writer.drain()


async def send_message(writer: asyncio.StreamWriter,
                       sending_queue: asyncio.Queue,
                       watchdog_queue: asyncio.Queue) -> None:
    while True:
        message = await sending_queue.get()
        await submit_message(writer, message)
        await watchdog_queue.put("Message sent")


async def submit_message(writer: asyncio.StreamWriter,
                         message: str) -> None:
    message = ''.join(message).replace('\n', ' ') + '\n'
    await _write_and_log(writer, message)


async def ping_pong(reader: asyncio.StreamReader,
                    writer: asyncio.StreamWriter,
                    watchdog_queue: asyncio.Queue) -> None:
    async with create_handy_nursery() as nursery:
        nursery.start_soon(
            _ping(writer)
        )
        nursery.start_soon(
            _pong(reader, watchdog_queue)
        )


async def _ping(writer: asyncio.StreamWriter) -> None:
    while True:
        writer.write(b'\n')
        await writer.drain()
        await asyncio.sleep(PING_TIMEOUT)


async def _pong(reader: asyncio.StreamReader,
                watchdog_queue: asyncio.Queue) -> None:
    while True:
        await reader.readline()
        await watchdog_queue.put("PING")


async def registration(reader: asyncio.StreamReader,
                       writer: asyncio.StreamWriter,
                       status_queue: asyncio.Queue) -> str:
    login_queue = asyncio.Queue(maxsize=1)
    async with create_handy_nursery() as nursery:
        nursery.start_soon(register_draw(login_queue))
        tok = nursery.start_soon(register(
            reader, writer, login_queue, status_queue))
    return tok.result()


async def register(reader: asyncio.StreamReader,
                   writer: asyncio.StreamWriter,
                   login_queue: asyncio.Queue,
                   status_queue: asyncio.Queue) -> str:
    login = await login_queue.get()
    _ = await _read_and_log(reader)
    await _write_and_log(writer, '')
    _ = await _read_and_log(reader)
    await _write_and_log(writer, login)
    user_data = await _read_and_log(reader)
    user_data = json.loads(user_data)
    token = user_data["account_hash"]
    user = user_data["nickname"]
    messagebox.showinfo("registration successful",
                        "Your token: {}\nYour nickname: {}"
                        .format(token, user))
    return token, user
