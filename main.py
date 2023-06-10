import os
import random
import sys
import time
from asyncio import StreamWriter, StreamReader

import numpy as np
import numpy.typing as npt
import scipy
import asyncio

import skimage.segmentation

np.set_printoptions(threshold=sys.maxsize, linewidth=sys.maxsize)

# HOSTNAME = "gpn-tron.duckdns.org"
HOSTNAME = "94.45.236.142"
PORT = 4000

EMPTY = 0
MASK = np.array([[1, 1, 1],
                 [1, 0, 1],
                 [1, 1, 1]], dtype=np.float32)

MESSAGES = [
    "Powered by numpy!",
    "Powered by scipy!",
    "Powered by skimage!",
    "Powered by asyncio!",
    "Powered by match statements!",
    "Python fast!",
    #"Uses convolutions (poorly)",
    "cha bu duo",
    "No unicode in chat :(",
    "Sends messages every 3 seconds"
]


class TronBot:
    reader: StreamReader
    writer: StreamWriter
    width: int
    height: int
    player_id: int
    position: tuple[int, int]
    field: npt.NDArray[np.int32]
    heads: npt.NDArray[np.int32]

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
                    self.player_id = int(player_id) + 1
                    await self.start_game()
                case _:
                    print(f'Unhandled message: {message}')

    async def start_game(self):
        print(f"game starting, we are {self.player_id}")
        self.field = np.full((self.width, self.height), EMPTY, dtype=np.int32)
        self.heads = np.full((self.width, self.height), EMPTY, dtype=np.int32)
        tick = 0
        now = time.time()

        while True:
            message = await self.read_message()
            if not message:
                continue

            match message:
                case ["win", wins, losses]:
                    print(f"WIN :) ({wins}:{losses})")
                    return
                case ["lose", wins, losses]:
                    print(f"LOSE :( ({wins}:{losses})")
                    return
                case ["pos", player_id, x, y]:
                    player_id = int(player_id) + 1
                    x = int(x)
                    y = int(y)
                    self.heads[y, x] = player_id
                    if player_id == self.player_id:
                        self.position = (y, x)
                case ["die", *players]:
                    players = [int(player_id) + 1 for player_id in players]
                    self.field[np.where(np.isin(self.field, players))] = EMPTY
                case ["tick"]:
                    start = time.time_ns()
                    self.field += self.heads
                    tick += 1
                    if time.time() - now > 3:
                        await self.send_message("chat", random.choice(MESSAGES))
                        now = time.time()
                    direction = self.find_move(True)
                    await self.send_message("move", direction)
                    print(f"Handled tick in {round((time.time_ns() - start) / 1_000_000, 2)} milliseconds.")
                    self.heads = np.full((self.width, self.height), EMPTY, dtype=np.int32)
                case ["error", message]:
                    print(f"Error: {message}")
                    return
                case ["message", player_id, message]:
                    pass
                case ["player", player_id, name]:
                    pass
                case _:
                    print(f'Unhandled message: {message}')

    def find_move(self, shuffle: bool):
        # danger = self.get_danger_map()
        regions = self.get_regions_map()

        directions = ["up", "down", "left", "right"]
        if shuffle:
            random.shuffle(directions)
        best_score = 0
        best_direction = "up"
        for direction in directions:
            print(f"Checking direction {direction}")
            new_position = self.move(self.position, direction)
            if self.field[*new_position] != EMPTY:
                # This move would make us instantly lose
                continue
            new_region = regions[*new_position]
            if new_region == 0:
                score = 1
            else:
                score = np.count_nonzero(regions == regions[*new_position])
            print(score)
            if score > best_score:
                best_score = score
                best_direction = direction
        return best_direction

    def get_danger_map(self):
        heads = np.copy(self.heads)
        heads[heads == self.player_id] = 0
        return scipy.signal.convolve2d(heads, MASK, mode="same", boundary='wrap')

    def get_regions_map(self):
        field = np.copy(self.field)
        heads = np.copy(self.heads)
        heads[heads == self.player_id] = 0
        heads = scipy.ndimage.binary_dilation(heads).astype(field.dtype)
        field += heads
        field[field == 0] = -1
        field[field != -1] = EMPTY
        regions, num_features = scipy.ndimage.label(field)
        for i in range(regions.shape[0]):
            if regions[i][0] != regions[i][-1] and regions[i][0] != EMPTY and regions[i][-1] != EMPTY:
                regions = skimage.segmentation.flood_fill(regions, (i, -1), regions[i, 0])
        for i in range(regions.shape[1]):
            if regions[0][i] != regions[-1][i] and regions[0][i] != EMPTY and regions[-1][i] != EMPTY:
                regions = skimage.segmentation.flood_fill(regions, (-1, i), regions[0, i])

        return regions

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
        # print(f"Sending {command}, {arguments}")
        self.writer.write(f"{'|'.join([command, *arguments])}\n".encode())
        await self.writer.drain()


if __name__ == '__main__':
    bot = TronBot()
    asyncio.run(bot.run())
