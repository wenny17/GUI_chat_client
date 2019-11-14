import time
import asyncio
import logging
import json
from contextlib import  suppress
from tkinter import messagebox

from async_timeout import timeout

import gui
from utils import connect_to_addr, create_handy_nursery
from exceptions import InvalidToken
from registration_gui import draw_register_window

PACKETS_TIMEOUT = 4
PING_TIMEOUT = 1


async def read_msgs(
                    host,
                    port,
                    messages_queue,
                    status_queue,
                    history_queue,
                    watchdog_queue
                    ):
    conn_mode = gui.ReadConnectionStateChanged
    async with connect_to_addr(host, port, status_queue, conn_mode) as (reader, _):
        while True:
            data = await reader.readline()

            data = data.decode("utf-8")
            messages_queue.put_nowait(data.strip())
            history_queue.put_nowait(data)
            watchdog_queue.put_nowait("New message in chat")


async def send_msgs(
                    host,
                    port,
                    sending_queue,
                    status_queue,
                    watchdog_queue,
                    token
                    ):
    if not token["token"]:
        token["token"] = await register_new_user(host, port, status_queue)

    token = token["token"]
    conn_mode = gui.SendingConnectionStateChanged
    async with connect_to_addr(host, port, status_queue, conn_mode) as (reader, writer):
        watchdog_queue.put_nowait("Prompt before auth")
        await authorise(reader, writer, status_queue, token)
        watchdog_queue.put_nowait("Authorization done")

        lock = asyncio.Lock()
        async with create_handy_nursery() as nursery:
            nursery.start_soon(send_message(reader, writer, sending_queue, watchdog_queue, lock))
            nursery.start_soon(ping_pong(reader, writer, watchdog_queue, lock))


async def watch_for_connection(watchdog_queue):
    log = logging.getLogger("watchdog")
    while True:
        with suppress(asyncio.TimeoutError):
            async with timeout(PACKETS_TIMEOUT) as cm:
                action = await watchdog_queue.get()
        if cm.expired:
            log.debug(f"[{time.time()}] {PACKETS_TIMEOUT}s timeout is elapsed")
            raise ConnectionError
        log.debug(f"[{time.time()}] Connection is alive. {action}")

async def send_message(reader, writer, sending_queue, watchdog_queue, lock):
    while True:
        message = await sending_queue.get()
        async with lock:
            await submit_message(reader, writer, message)
        watchdog_queue.put_nowait("Message sent")


async def ping_pong(reader, writer, watchdog_queue, lock):
    while True:
        async with lock:
            await submit_message(reader, writer, '')
        watchdog_queue.put_nowait("PING")
        await asyncio.sleep(PING_TIMEOUT)


async def read_and_log(reader):
    message = (await reader.readline()).decode('utf-8')
    logging.debug("RECEIVE: {}".format(message))
    return message


async def write_and_log(writer, message):
    writer.write(message.encode() + b'\n')
    logging.debug("SEND: {}".format(message))
    await writer.drain()


async def authorise(reader, writer, status_queue, token):
    entry_message = await read_and_log(reader)
    await write_and_log(writer, token)
    message = await read_and_log(reader)
    auth_response = json.loads(message)
    if not auth_response:
        raise InvalidToken
    user = auth_response["nickname"]
    status_queue.put_nowait(gui.NicknameReceived(user))
    logging.debug(f"authorization done. User: {user}")
    message = await read_and_log(reader)



async def submit_message(reader, writer, message):
    message = ''.join(message).replace('\n', ' ') + '\n'
    await write_and_log(writer, message)
    message = await read_and_log(reader)


async def register_new_user(host, port, status_queue):
    status_queue.put_nowait(gui.SendingConnectionStateChanged.CLOSED)
    login_queue = asyncio.Queue(maxsize=1)
    async with create_handy_nursery() as nursery:
        nursery.start_soon(draw_register_window(login_queue))
        tok = nursery.start_soon(register(host, port, login_queue, status_queue))
    return tok.result()


async def register(host, port, login_queue, status_queue):
    conn_mode = gui.SendingConnectionStateChanged
    login = await login_queue.get()
    async with connect_to_addr(host, port, status_queue, conn_mode) as (reader, writer):
        entry_message = await read_and_log(reader)
        await write_and_log(writer, '')
        message = await read_and_log(reader)
        await write_and_log(writer, login)
        user_data = await read_and_log(reader)
        user_data = json.loads(user_data)
        token = user_data["account_hash"]
        user = user_data["nickname"]
        status_queue.put_nowait(gui.NicknameReceived(user))
        status_queue.put_nowait(gui.SendingConnectionStateChanged.ESTABLISHED)
        messagebox.showinfo("registration successful", "Your token: {}\nYour nickname: {}".format(token, user))
        return token
