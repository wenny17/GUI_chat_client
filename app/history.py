import asyncio
import datetime

import aiofiles


async def save_messages(filepath: str, history_queue: asyncio.Queue) -> None:
    async with aiofiles.open(filepath, 'a') as f:
        while True:
            data = await history_queue.get()
            now = datetime.datetime.now()
            time = now.strftime("%d.%m.%Y %H:%M")
            message = "[{}] {}".format(time, data)
            await f.write(message + '\n')


def load_history(history_directory: str, msg_queue: asyncio.Queue) -> None:
    with open(history_directory, "a+") as f:
        f.seek(0)
        for line in f.readlines():
            msg_queue.put_nowait(line.strip())
