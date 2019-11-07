import asyncio
import time
import os
import datetime
import json
import logging
from contextlib import suppress
import socket
from tkinter import messagebox

import aiofiles
from dotenv import load_dotenv
import gui
from utils import ConnectToRead, ConnectToWrite
from async_timeout import timeout
import aionursery


class InvalidToken(Exception):
    pass

async def write_and_logg(writer, message):
    writer.write(message.encode() + b'\n')
    logging.debug("SEND: {}".format(message))
    await writer.drain()


async def read_and_log(reader):
    message = (await reader.readline()).decode('utf-8')
    logging.debug("RECEIVE: {}".format(message))
    return message



async def submit_message(reader, writer, message):
    message = ''.join(message).replace('\n', ' ') + '\n'
    await write_and_logg(writer, message)
    message = await read_and_log(reader)


async def authorise(reader, writer, status_queue, token, ):
    entry_message = await read_and_log(reader)
    await write_and_logg(writer, token)
    message = await read_and_log(reader)
    auth_response = json.loads(message)
    if not auth_response:
        return False
    user = auth_response["nickname"]
    status_queue.put_nowait(gui.NicknameReceived(user))
    logging.debug(f"Выполнена авторизация. Пользователь {user}")
    message = await read_and_log(reader)
    return True


async def send_msgs(host, port, sending_queue, status_queue, watchdog_queue, token):
    while True:
        async with ConnectToWrite(host, port, status_queue) as (reader,writer):
            watchdog_queue.put_nowait("Prompt before auth")
            is_authorise = await authorise(reader, writer, status_queue, token)
            if not is_authorise:
                messagebox.showinfo("Неверный токен", "Проверьте токен, сервер его не узнал.")
                raise InvalidToken
            watchdog_queue.put_nowait("Authorization done")
            while True:
                message = await sending_queue.get()
                try:
                    await asyncio.wait_for(submit_message(reader, writer, message), timeout=3)
                    watchdog_queue.put_nowait("Message sent")
                except asyncio.TimeoutError:
                    break


async def read_msgs(host, port, message_queue, status_queue, history_queue, watchdog_queue):
    while True:
        async with ConnectToRead(host, port, status_queue) as (reader, writer):
            while True:
                try:
                    data = await asyncio.wait_for(reader.readline(), timeout=3)
                except asyncio.TimeoutError:
                    await asyncio.sleep(1)
                    break
                data = data.decode("utf-8")
                message_queue.put_nowait(data)
                history_queue.put_nowait(data)
                watchdog_queue.put_nowait("New message in chat")



async def save_messages(filepath, queue):
    while True:
        data = await queue.get()
        async with aiofiles.open(filepath, 'a') as f:
            now = datetime.datetime.now()
            time = now.strftime("%d.%m.%Y %H:%M")
            message = "[{}] ".format(time) + data
            await f.write(message)


async def watch_for_connection(watchdog_queue):
    while True:
        action = await watchdog_queue.get()
        logging.debug(f"[{time.time()}] Connection is alive. {action}")

def get_args():
    host = os.getenv("HOST")
    port = os.getenv("PORT_READ")
    return host, port


def load_history(queue):
    history = os.getenv("HISTORY_DIRECTORY")
    with open(history) as f:
        for line in f.readlines():
            queue.put_nowait(line)


async def handle_connection(host, port,
                            messages_queue,
                            status_updates_queue,
                            history_queue,
                            watchdog_queue,
                            sending_queue,
                            token):
    async with aionursery.Nursery() as nursery:
        nursery.start_soon(read_msgs(host, port,
                                      messages_queue,
                                      status_updates_queue,
                                      history_queue,
                                      watchdog_queue))
        nursery.start_soon(send_msgs(host, 5050,
                                      sending_queue,
                                      status_updates_queue,
                                      watchdog_queue,
                                      token))
        nursery.start_soon(watch_for_connection(watchdog_queue))

async def main():
    load_dotenv()
    logging.basicConfig(level = logging.DEBUG, filename="logging.log")
    host, port = get_args()
    token = os.getenv("TOKEN")

    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()
    history_queue = asyncio.Queue()
    watchdog_queue = asyncio.Queue()

    load_history(messages_queue)

    await asyncio.gather(
        gui.draw(messages_queue, sending_queue, status_updates_queue),
        handle_connection(host, port,
                            messages_queue,
                            status_updates_queue,
                            history_queue,
                            watchdog_queue,
                            sending_queue,
                            token),
        save_messages(os.getenv("HISTORY_DIRECTORY"), history_queue)
    )

if __name__ == '__main__':
    with suppress(KeyboardInterrupt, gui.TkAppClosed, InvalidToken):
        asyncio.run(main())

