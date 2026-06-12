import asyncio
import websockets
import json

class WebSocketSender:
    URI = "ws://localhost:5000/"

    @staticmethod
    async def _send(data):
        async with websockets.connect(WebSocketSender.URI) as websocket:
            if isinstance(data, dict):
                data = json.dumps(data)

            await websocket.send(data)

    @staticmethod
    def send(data):
        asyncio.run(WebSocketSender._send(data))