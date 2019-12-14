from contextlib import asynccontextmanager
from enum import Enum

import aionursery


class Token:
    def __init__(self, token: str) -> None:
        self.value = token

    @property
    def is_exist(self) -> bool:
        return True if self.value else False


class WatchdogSwitcher(Enum):
    ENABLE = True
    DISABLE = False


@asynccontextmanager
async def create_handy_nursery() -> aionursery.Nursery:
    try:
        async with aionursery.Nursery() as nursery:
            yield nursery
    except aionursery.MultiError as e:
        if len(e.exceptions) == 1:
            raise e.exceptions[0] from None
        raise


def filter_bots(message: str) -> bool:
    adresser = message.split(':')[0]
    return adresser in ('Vlad', 'Eva')
