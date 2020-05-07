#!/usr/bin/env python
from weakref import WeakSet
import trio
from trio_websocket import serve_websocket, ConnectionClosed
import logging
logging.basicConfig(level=logging.INFO)


class Client:
    # keep tracking of the client instances
    def __new__(cls, *args, **kwargs):
        instance = object.__new__(cls)
        if "instances" not in cls.__dict__:
            cls.instances = WeakSet()
        cls.instances.add(instance)
        return instance

    def __init__(self, web_socket, name):
        self.web_socket = web_socket
        self.name = name
        # create a memory channel for interactions with other clients
        self.send_channel, self.receive_channel = trio.open_memory_channel(0)

    async def redirect_from_web_socket_to_all_clients(self):
        async with self.send_channel:
            while True:
                message = await self.web_socket.get_message()
                message = f"{self.name}: {message}"
                async with trio.open_nursery() as nursery:
                    for client in Client.instances:
                        if not client == self:
                            nursery.start_soon(client.send_channel.send, message)

    async def redirect_memory_channel_to_web_socket(self):
        async with self.receive_channel:
            async for message in self.receive_channel:
                await self.web_socket.send_message(message)

    @staticmethod
    async def broadcast(message):
        async with trio.open_nursery() as nursery:
            for client in Client.instances:
                nursery.start_soon(client.send_channel.send, message)


async def handler(request):
    """ web-socket connection handler """
    ws = await request.accept()
    logging.info("new connection")
    try:
        # ask Human about his name:
        await ws.send_message("What is your name?")
        name = await ws.get_message()
        name = name.strip()
        await ws.send_message(f"Welcome to the chat, {name}")
        logging.info(f"{name} is connected.")
    except ConnectionClosed:
        logging.info("Server tried to ask user name, but connection was closed.")
        return

    client = Client(ws, name)
    try:
        async with trio.open_nursery() as nursery:
            nursery.start_soon(client.redirect_from_web_socket_to_all_clients)
            nursery.start_soon(client.redirect_memory_channel_to_web_socket)

    except ConnectionClosed:
        message = f"Server: {client.name} disconnected."
        logging.info(message)
        # delete client instance
        Client.instances.remove(client)
        del client
        # notify people in the chat
        await Client.broadcast(message)


async def main():
    await serve_websocket(handler, '127.0.0.1', 8000, ssl_context=None)


trio.run(main)
