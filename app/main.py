import asyncio
import logging
from tkinter import messagebox

import aionursery

import args
import history
import connection
from exceptions import InvalidToken
from utils import create_handy_nursery, Token
import gui

RECONNECT_DELAY = 1


async def handle_connection(host: str,
                            reader_port: int,
                            writer_port: int,
                            token: str,
                            messages_queue: asyncio.Queue,
                            status_queue: asyncio.Queue,
                            history_queue: asyncio.Queue,
                            sending_queue: asyncio.Queue,
                            watchdog_queue: asyncio.Queue) -> None:
    token = Token(token)
    while True:
        try:
            async with create_handy_nursery() as nursery:
                nursery.start_soon(
                    connection.read_msgs(
                        host=host,
                        port=reader_port,
                        messages_queue=messages_queue,
                        status_queue=status_queue,
                        history_queue=history_queue,
                        watchdog_queue=watchdog_queue
                    )
                )
                nursery.start_soon(
                    connection.send_msgs(
                        host=host,
                        port=writer_port,
                        token=token,
                        sending_queue=sending_queue,
                        status_queue=status_queue,
                        watchdog_queue=watchdog_queue
                    )
                )
                nursery.start_soon(
                    connection.watch_for_connection(
                        watchdog_queue=watchdog_queue
                    )
                )
        except aionursery.MultiError as e:
            if not any(isinstance(ex, ConnectionError) for ex in e.exceptions):
                raise
        except ConnectionError:
            await asyncio.sleep(RECONNECT_DELAY)
        else:
            return


async def run_app(host: str,
                  reader_port: int,
                  writer_port: int,
                  token: str,
                  history_path: str) -> None:

    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()
    history_queue = asyncio.Queue()
    watchdog_queue = asyncio.Queue()

    history.load_history(history_path, messages_queue)

    async with create_handy_nursery() as nursery:
        nursery.start_soon(
            gui.draw(
                messages_queue,
                sending_queue,
                status_updates_queue
            )
        )
        nursery.start_soon(
            history.save_messages(
                filepath=history_path,
                history_queue=history_queue
            )
        )
        nursery.start_soon(
            handle_connection(
                host=host,
                reader_port=reader_port,
                writer_port=writer_port,
                token=token,
                messages_queue=messages_queue,
                status_queue=status_updates_queue,
                history_queue=history_queue,
                sending_queue=sending_queue,
                watchdog_queue=watchdog_queue
            )
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s-%(message)s')
    params = args.get_args()

    try:
        asyncio.run(
            run_app(
                host=params.host,
                reader_port=params.port,
                writer_port=params.portw,
                token=params.token,
                history_path=params.history
            )
        )
    except InvalidToken:
        messagebox.showinfo("Wrong Token", "Enter a valid token")
    except (KeyboardInterrupt,
            gui.TkAppClosed):
        exit(0)


if __name__ == '__main__':
    main()
