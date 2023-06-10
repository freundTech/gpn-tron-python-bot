import os
import random
import sys
from asyncio import StreamWriter, StreamReader

import numpy as np
import asyncio

np.set_printoptions(threshold=sys.maxsize, linewidth=sys.maxsize)

HOSTNAME = "2001:67c:20a1:232:c5bb:64f8:b45f:9c38"
PORT = 4000


class TronBot:
    reader: StreamReader
    writer: StreamWriter
    width: int
    height: int
    player_id: int
    position: tuple[int, int]

    async def run(self):
        username = os.environ["GPN_TRON_USERNAME"]
        password = os.environ["GPN_TRON_PASSWORD"]
        try:
            self.reader, self.writer = await asyncio.open_connection(HOSTNAME, PORT)
        except ConnectionRefusedError:
            print("Unable to connect to the server.")

        while True:
            message = await self.read_message()
            if not message:
                continue

            match message:
                case ["motd", motd]:
                    print(f"Message of the day: {motd}")
                    await self.send_message("join", username, password)
                case ["error", message]:
                    print(f"Error: {message}")
                    return
                case ["game", width, height, player_id]:
                    self.width = int(width)
                    self.height = int(height)
                    self.player_id = int(player_id)
                    await self.start_game()
                case _:
                    print(f'Unhandled message: {message}')

    async def start_game(self):
        print(f"game starting, we are {self.player_id}")
        field = np.full((self.width, self.height), 0, dtype=np.int32)

        while True:
            message = await self.read_message()
            if not message:
                continue

            match message:
                case ["win", wins, losses]:
                    print("won")
                    return
                case ["lose", wins, losses]:
                    print("lost")
                    return
                case ["pos", player_id, x, y]:
                    player_id = int(player_id)
                    x = int(x)
                    y = int(y)
                    field[y, x] = player_id
                    if player_id == self.player_id:
                        position = (y, x)
                case ["die", *players]:
                    players = [int(player_id) for player_id in players]
                    field[np.where(np.isin(field, players))] = 0
                case ["tick"]:
                    print(field)
                    directions = ["up", "down", "left", "right"]
                    random.shuffle(directions)
                    for direction in directions:
                        print(f"Checking direction {direction}")
                        new_position = self.move(position, direction)
                        if field[*new_position] == 0:
                            await self.send_message("move", direction)
                            break
                case ["error", message]:
                    print(f"Error: {message}")
                    return
                case ["message", message]:
                    pass
                case _:
                    print(f'Unhandled message: {message}')

    def move(self, position, direction):
        match direction:
            case "up":
                return (position[0] - 1) % self.height, position[1]
            case "down":
                return (position[0] + 1) % self.height, position[1]
            case "left":
                return position[0], (position[1] - 1) % self.width
            case "right":
                return position[0], (position[1] + 1) % self.width

    async def read_message(self):
        line = await self.reader.readline()
        message = line.decode()
        if message.endswith("\n"):
            message = message[:-1]

        return message.split("|")

    async def send_message(self, command: str, *arguments: str):
        print(f"Sending {command}, {arguments}")
        self.writer.write(f"{'|'.join([command, *arguments])}\n".encode())
        await self.writer.drain()


if __name__ == '__main__':
    bot = TronBot()
    asyncio.run(bot.run())
