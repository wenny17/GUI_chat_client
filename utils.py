import asyncio
import socket
import logging
import gui

class Connect:
    def __init__(self, host, port, status_queue=None):
        self.host = host
        self.port = port
        self.status_queue = status_queue
        self.reader = None
        self.writer = None
        self.conn_state_mode = None


    async def connect(self):
        connection_attempts = 0
        while True:
            try:
                self.status_queue.put_nowait(self.conn_state_mode.INITIATED)
                reader, writer = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), timeout=60)
                self.status_queue.put_nowait(self.conn_state_mode.ESTABLISHED)
                print("Установлено соединение\n")
                return reader, writer

            except (asyncio.TimeoutError,
                    socket.gaierror,
                    ConnectionRefusedError,
                    ConnectionResetError):
                self.status_queue.put_nowait(self.conn_state_mode.INITIATED)
                connection_attempts += 1

                if connection_attempts < 3:
                    print("Нет соединения. Повторная попытка.\n")
                else:
                    self.status_queue.put_nowait(self.conn_state_mode.CLOSED)
                    print("Нет соединения. Повторная попытка через 3 сек.\n")
                    await asyncio.sleep(3)


    async def __aenter__(self):
        self.reader, self.writer = await self.connect()
        return self.reader, self.writer

    async def __aexit__(self, exc_type, exc, tb):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()


class ConnectToRead(Connect):
    def __init__(self, host, port, queue):
        super().__init__(host, port, queue)
        self.conn_state_mode = gui.ReadConnectionStateChanged


class ConnectToWrite(Connect):
    def __init__(self, host, port, queue):
        super().__init__(host, port, queue)
        self.conn_state_mode = gui.SendingConnectionStateChanged
