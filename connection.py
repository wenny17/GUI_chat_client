import asyncio
import time
import logging

import async_timeout

import gui
from connection_utils import registration
from utils import create_handy_nursery, Token, WatchdogSwitcher, filter_bots
from connection_utils import (
    authorise,
    connect,
    send_message,
    ping_pong,
)


PACKETS_TIMEOUT = 2


async def read_msgs(host: str,
                    port: int,
                    messages_queue: asyncio.Queue,
                    status_queue: asyncio.Queue,
                    history_queue: asyncio.Queue,
                    watchdog_queue: asyncio.Queue,
                    enable_bots=False) -> None:
    async with connect(
        host=host,
        port=port,
        status_queue=status_queue,
        connect_state_mode=gui.ReadConnectionStateChanged
    ) as (reader, _):
        while True:
            data = await reader.readline()
            message = data.decode("utf-8").strip()
            if not enable_bots and filter_bots(message):
                continue

            await history_queue.put(message)
            await messages_queue.put(message)
            await watchdog_queue.put("New message in chat")


async def send_msgs(host: str,
                    port: int,
                    token: Token,
                    sending_queue: asyncio.Queue,
                    status_queue: asyncio.Queue,
                    watchdog_queue: asyncio.Queue) -> None:
    authorized = False
    async with connect(
        host=host,
        port=port,
        status_queue=status_queue,
        connect_state_mode=gui.SendingConnectionStateChanged
    ) as (reader, writer):

        if not token.is_exist:
            status_queue.put_nowait(gui.SendingConnectionStateChanged.CLOSED)
            token.value, user = await registration(reader, writer, status_queue)
            status_queue.put_nowait(gui.SendingConnectionStateChanged.INITIATED)
            authorized = True
        await watchdog_queue.put(WatchdogSwitcher.ENABLE)

        if not authorized:
            await watchdog_queue.put("Prompt before auth")
            user = await authorise(reader, writer, token.value)

        await status_queue.put(gui.NicknameReceived(user))
        await watchdog_queue.put("Authorization done")
        status_queue.put_nowait(gui.SendingConnectionStateChanged.ESTABLISHED)

        async with create_handy_nursery() as nursery:
            nursery.start_soon(
                send_message(
                    writer=writer,
                    sending_queue=sending_queue,
                    watchdog_queue=watchdog_queue
                )
            )
            nursery.start_soon(
                ping_pong(reader, writer, watchdog_queue)
            )


async def watch_for_connection(watchdog_queue: asyncio.Queue,
                               enable_watchdog=False) -> None:
    while True:
        if enable_watchdog:
            try:
                async with async_timeout.timeout(PACKETS_TIMEOUT) as cm:
                    action = await watchdog_queue.get()
                    if isinstance(action, WatchdogSwitcher):
                        enable_watchdog = action.value
                        continue
            except asyncio.TimeoutError:
                if cm.expired:
                    now = time.time()
                    logging.info(
                        f"[{now}] {PACKETS_TIMEOUT}s timeout is elapsed"
                    )
                    raise ConnectionError
            logging.info(f"[{time.time()}] Connection is alive. {action}")
        else:
            action = await watchdog_queue.get()
            if isinstance(action, WatchdogSwitcher):
                enable_watchdog = action.value
