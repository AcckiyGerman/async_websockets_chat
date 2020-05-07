#!/usr/bin/env python
import trio
from sys import stderr
from trio_websocket import open_websocket_url


async def web_socket_to_stdout(web_socket):
    while True:
        message = await web_socket.get_message()
        print(message)


async def stdin_to_web_socket(web_socket):
    async with await trio.open_file(0) as file:
        async for message in file:
            await web_socket.send_message(message)


async def main():
    try:
        async with open_websocket_url('ws://localhost:8000/') as ws:
            async with trio.open_nursery() as nursery:
                nursery.start_soon(web_socket_to_stdout, ws)
                nursery.start_soon(stdin_to_web_socket, ws)
    except OSError as ose:
        print('Connection attempt failed: %s' % ose, file=stderr)

trio.run(main)
