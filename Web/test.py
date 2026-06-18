import asyncio
import datetime
import websockets

async def send_date(websocket):
    print(f"Client connected: {websocket.remote_address}")
    try:
        while True:
            # Get current date and time
            now = "39.67613248015898,-104.9589952429265";
            # Send it to the client
            await websocket.send(now)
            
            # Wait for 1 second before sending the next update
            await asyncio.sleep(1)
    except websockets.ConnectionClosed:
        print(f"Client disconnected: {websocket.remote_address}")

async def main():
    # Start the server on localhost, port 8765
    async with websockets.serve(send_date, "localhost", 2020):
        print("WebSocket server started on ws://localhost:2020")
        await asyncio.Future() # Run forever

if __name__ == "__main__":
    asyncio.run(main())