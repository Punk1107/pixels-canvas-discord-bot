import asyncio
from config import CANVAS_WIDTH, CANVAS_HEIGHT, PIXEL_SCALE

# Mock the database pixels
mock_pixels = [{"x": i, "y": i, "color": "red"} for i in range(10)]

from canvas.renderer import canvas_cache

async def test_lock():
    print("Testing build_from_db...")
    await canvas_cache.build_from_db(mock_pixels)
    
    print("Testing get_image_bytes...")
    buf = await canvas_cache.get_image_bytes()
    print(f"Image size: {len(buf.getvalue())} bytes")
    
    print("Testing concurrent access...")
    async def fast_updater():
        for i in range(5):
            await canvas_cache.update_pixel(1, 1, "blue")
            await asyncio.sleep(0.1)
            
    async def slow_reader():
        for i in range(2):
            buf = await canvas_cache.get_image_bytes()
            await asyncio.sleep(0.2)
            
    await asyncio.gather(fast_updater(), slow_reader())
    print("Lock concurrency test passed without TypeErrors!")

if __name__ == "__main__":
    asyncio.run(test_lock())
