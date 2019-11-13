import time
import os
import asyncio
import argparse
import datetime
import logging
from contextlib import suppress
from tkinter import messagebox

from dotenv import load_dotenv
import aiofiles

import gui
from utils import create_handy_nursery
from exceptions import InvalidToken
import connection_utils as conn_utils


DEFAULT_HISTORY_DIR = "chathistory.txt"
DEFAULT_HOST = "minechat.dvmn.org"
DEFAULT_PORT_R = 5000
DEFAULT_PORT_W = 5050


async def handle_connection(
                            host,
                            port_r,
                            port_w,
                            messages_queue,
                            status_queue,
                            history_queue,
                            sending_queue,
                            token
                            ):
    watchdog_queue = asyncio.Queue()
    token_queue = asyncio.Queue(maxsize=1)
    token = {"token": token}

    while True:
        with suppress(ConnectionError):
            async with create_handy_nursery() as nursery:
                nursery.start_soon(conn_utils.read_msgs(
                                                        host,
                                                        port_r,
                                                        messages_queue,
                                                        status_queue,
                                                        history_queue,
                                                        watchdog_queue
                                                        )
                )
                nursery.start_soon(conn_utils.send_msgs(
                                                        host,
                                                        port_w,
                                                        sending_queue,
                                                        status_queue,
                                                        watchdog_queue,
                                                        token
                                                        )
                )
                nursery.start_soon(conn_utils.watch_for_connection(watchdog_queue))



async def save_messages(filepath, queue):
    async with aiofiles.open(filepath, 'a') as f:
        while True:
            data = await queue.get()
            now = datetime.datetime.now()
            time = now.strftime("%d.%m.%Y %H:%M")
            message = "[{}] ".format(time) + data
            await f.write(message)


def load_history(queue, history_directory):
    with open(history_directory) as f:
        for line in f.readlines():
            queue.put_nowait(line.strip())


def get_args():
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("-token",
                        default=os.getenv("TOKEN"),
                        help="chat token, if you havent one, please register")
    parser.add_argument("-host",
                        default=os.getenv("HOST") or DEFAULT_HOST)
    parser.add_argument("-port",
                        default=os.getenv("READER_PORT") or DEFAULT_PORT_R,
                        help="port for read messages")
    parser.add_argument("-portw",
                        default=os.getenv("WRITER_PORT") or DEFAULT_PORT_W,
                        help="port for send messages")
    parser.add_argument("-history",
                        default=os.getenv("HISTORY") or DEFAULT_HISTORY_DIR,
                        help="history file directory")
    return parser.parse_args()


async def main():
    formatter = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=logging.DEBUG,
                        filename="logging.log",
                        format=formatter)
    args = get_args()

    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()
    history_queue = asyncio.Queue()


    load_history(messages_queue, args.history)

    async with create_handy_nursery() as nursery:
        nursery.start_soon(gui.draw(
                                    messages_queue,
                                    sending_queue,
                                    status_updates_queue
                                    )
        )
        nursery.start_soon(handle_connection(
                                             args.host,
                                             args.port,
                                             args.portw,
                                             messages_queue,
                                             status_updates_queue,
                                             history_queue,
                                             sending_queue,
                                             args.token
                                             )
        )
        nursery.start_soon(save_messages(args.history, history_queue))


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except InvalidToken:
        messagebox.showinfo("Wrong Token", "Enter a valid token")
    except (KeyboardInterrupt,
            gui.TkAppClosed):
        exit(0)
