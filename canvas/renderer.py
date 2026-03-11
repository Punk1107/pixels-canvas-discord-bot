from PIL import Image, ImageDraw, ImageColor
import io
import asyncio
from contextlib import asynccontextmanager
from config import CANVAS_WIDTH, CANVAS_HEIGHT, PIXEL_SCALE
import logging

logger = logging.getLogger(__name__)

def is_valid_color(color_str: str) -> bool:
    """Helper method to check if a color string is valid according to PIL."""
    try:
        ImageColor.getrgb(color_str)
        return True
    except ValueError:
        return False

class CanvasCache:
    def __init__(self):
        # Maps guild_id -> PIL Image
        self.images = {}
        # Maps guild_id -> ImageDraw
        self.draws = {}
        # Maps guild_id -> asyncio.Lock
        self.locks = {}
        # Maps guild_id -> io.BytesIO
        self._cached_images_bytes = {}
        # Maps guild_id -> bool
        self._needs_render = {}
        
        self.heavy_semaphore = asyncio.Semaphore(3)  # Maximum 3 concurrent giant image tasks
        
    def _init_guild_canvas(self, guild_id: int):
        if guild_id not in self.images:
            img = Image.new('RGB', (CANVAS_WIDTH * PIXEL_SCALE, CANVAS_HEIGHT * PIXEL_SCALE), color='white')
            draw = ImageDraw.Draw(img)
            
            # Draw initial grid
            for x in range(0, CANVAS_WIDTH * PIXEL_SCALE, PIXEL_SCALE):
                draw.line([(x, 0), (x, CANVAS_HEIGHT * PIXEL_SCALE)], fill='#E0E0E0', width=1)
            for y in range(0, CANVAS_HEIGHT * PIXEL_SCALE, PIXEL_SCALE):
                draw.line([(0, y), (CANVAS_WIDTH * PIXEL_SCALE, y)], fill='#E0E0E0', width=1)
                
            self.images[guild_id] = img
            self.draws[guild_id] = draw
            self.locks[guild_id] = asyncio.Lock()
            self._cached_images_bytes[guild_id] = None
            self._needs_render[guild_id] = True
            
    def _get_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self.locks:
            self._init_guild_canvas(guild_id)
        return self.locks[guild_id]

    @asynccontextmanager
    async def _lock_with_timeout(self, guild_id: int, timeout: float):
        lock = self._get_lock(guild_id)
        await asyncio.wait_for(lock.acquire(), timeout=timeout)
        try:
            yield
        finally:
            lock.release()
            
    async def build_from_db(self, pixels_data):
        """Build the initial canvas state from database records"""
        try:
            # We don't want to hold a lock for all guilds indefinitely, build sync dicts first
            guild_pixels = {}
            for record in pixels_data:
                g_id = record['guild_id']
                if g_id not in guild_pixels:
                    guild_pixels[g_id] = []
                guild_pixels[g_id].append(record)
                
            for guild_id, records in guild_pixels.items():
                self._init_guild_canvas(guild_id)
                async with self._lock_with_timeout(guild_id, 10.0):
                    for record in records:
                        x, y, color = record['x'], record['y'], record['color']
                        self._draw_pixel_sync(guild_id, x, y, color)
                    logger.info(f"Canvas for guild {guild_id} built with {len(records)} pixels")
                    
        except asyncio.TimeoutError:
            logger.error("Timeout: Failed to acquire canvas lock during build_from_db")
            
    def _draw_pixel_sync(self, guild_id: int, x: int, y: int, color: str):
        self._init_guild_canvas(guild_id)
        draw = self.draws[guild_id]
        
        x1 = x * PIXEL_SCALE
        y1 = y * PIXEL_SCALE
        x2 = x1 + PIXEL_SCALE
        y2 = y1 + PIXEL_SCALE
        
        try:
            draw.rectangle([x1, y1, x2, y2], fill=color)
        except ValueError:
            draw.rectangle([x1, y1, x2, y2], fill='black')
            
        self._needs_render[guild_id] = True

    async def update_pixel(self, guild_id: int, x: int, y: int, color: str):
        """Update a single pixel in the cache"""
        try:
            async with self._lock_with_timeout(guild_id, 5.0):
                self._draw_pixel_sync(guild_id, x, y, color)
        except asyncio.TimeoutError:
            logger.error(f"Timeout: Failed to acquire canvas lock to update pixel {x},{y} for guild {guild_id}")

    async def batch_update_pixels(self, guild_id: int, pixels_list):
        """Update multiple pixels instantly in memory."""
        try:
            async with self._lock_with_timeout(guild_id, 5.0):
                for x, y, color in pixels_list:
                    self._draw_pixel_sync(guild_id, x, y, color)
        except asyncio.TimeoutError:
            logger.error(f"Timeout: Failed to acquire canvas lock during batch update for guild {guild_id}")

    def _get_image_bytes_sync(self, guild_id: int) -> io.BytesIO:
        self._init_guild_canvas(guild_id)
        
        if not self._needs_render[guild_id] and self._cached_images_bytes[guild_id]:
            return io.BytesIO(self._cached_images_bytes[guild_id].getvalue())
            
        buffer = io.BytesIO()
        self.images[guild_id].save(buffer, format='PNG', optimize=True)
        self._cached_images_bytes[guild_id] = buffer
        self._needs_render[guild_id] = False
        
        return io.BytesIO(self._cached_images_bytes[guild_id].getvalue())

    def _get_zoomed_image_bytes_sync(self, guild_id: int, x: int, y: int, radius: int) -> io.BytesIO:
        self._init_guild_canvas(guild_id)
        img = self.images[guild_id]
        
        left = max(0, (x - radius) * PIXEL_SCALE)
        upper = max(0, (y - radius) * PIXEL_SCALE)
        right = min(CANVAS_WIDTH * PIXEL_SCALE, (x + radius + 1) * PIXEL_SCALE)
        lower = min(CANVAS_HEIGHT * PIXEL_SCALE, (y + radius + 1) * PIXEL_SCALE)
        
        cropped = img.crop((left, upper, right, lower))
        scaled = cropped.resize((cropped.width * 2, cropped.height * 2), Image.NEAREST)
        
        buffer = io.BytesIO()
        scaled.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer

    async def get_zoomed_image_bytes(self, guild_id: int, x: int, y: int, radius: int = 5) -> io.BytesIO:
        """Get a zoomed in crop of the canvas"""
        try:
            async with self.heavy_semaphore:
                async with self._lock_with_timeout(guild_id, 5.0):
                    return await asyncio.to_thread(self._get_zoomed_image_bytes_sync, guild_id, x, y, radius)
        except asyncio.TimeoutError:
            logger.error(f"Timeout: Failed to acquire canvas lock for get_zoomed_image for guild {guild_id}")
            # Return empty buffer safely rather than hanging discord interactions
            return io.BytesIO()

    def _generate_timelapse_gif_sync(self, history_data) -> io.BytesIO:
        # Create a blank white image
        base_img = Image.new('RGB', (CANVAS_WIDTH * PIXEL_SCALE, CANVAS_HEIGHT * PIXEL_SCALE), color='white')
        draw = ImageDraw.Draw(base_img)
        
        # Draw initial grid
        for x in range(0, CANVAS_WIDTH * PIXEL_SCALE, PIXEL_SCALE):
            draw.line([(x, 0), (x, CANVAS_HEIGHT * PIXEL_SCALE)], fill='#E0E0E0', width=1)
        for y in range(0, CANVAS_HEIGHT * PIXEL_SCALE, PIXEL_SCALE):
            draw.line([(0, y), (CANVAS_WIDTH * PIXEL_SCALE, y)], fill='#E0E0E0', width=1)
            
        frames = [base_img.copy()]
        
        if not history_data:
            buffer = io.BytesIO()
            frames[0].save(buffer, format='GIF', save_all=True)
            buffer.seek(0)
            return buffer
        
        # Batch pixels per frame so GIF isn't huge
        batch_size = max(1, len(history_data) // 50)  # rough target of 50-100 frames
        
        for i, record in enumerate(history_data):
            x = record['x'] * PIXEL_SCALE
            y = record['y'] * PIXEL_SCALE
            try:
                draw.rectangle([x, y, x + PIXEL_SCALE, y + PIXEL_SCALE], fill=record['color'])
            except ValueError:
                draw.rectangle([x, y, x + PIXEL_SCALE, y + PIXEL_SCALE], fill='black')
                
            if i > 0 and i % batch_size == 0:
                frames.append(base_img.copy())
                
        # Append final frame
        frames.append(base_img.copy())
        
        buffer = io.BytesIO()
        # Save as looping GIF
        frames[0].save(
            buffer,
            format='GIF',
            save_all=True,
            append_images=frames[1:],
            optimize=False,
            duration=100,  # 100ms per frame
            loop=0
        )
        buffer.seek(0)
        return buffer

    async def generate_timelapse_gif(self, guild_id: int, history_data) -> io.BytesIO:
        """Generate an animated GIF of the canvas history"""
        # We don't need a lock because we are not modifying or reading the active cache
        async with self.heavy_semaphore:
            return await asyncio.to_thread(self._generate_timelapse_gif_sync, history_data)

    async def get_image_bytes(self, guild_id: int) -> io.BytesIO:
        """Get the current canvas as a PNG byte buffer"""
        try:
            async with self.heavy_semaphore:
                async with self._lock_with_timeout(guild_id, 5.0):
                    return await asyncio.to_thread(self._get_image_bytes_sync, guild_id)
        except asyncio.TimeoutError:
            logger.error(f"Timeout: Failed to acquire canvas lock for get_image_bytes for guild {guild_id}")
            return io.BytesIO()

    async def reset(self, guild_id: int):
        """Reset the canvas back to white with grid"""
        try:
            async with self._lock_with_timeout(guild_id, 5.0):
                self._init_guild_canvas(guild_id)
                draw = self.draws[guild_id]
                draw.rectangle([0, 0, CANVAS_WIDTH * PIXEL_SCALE, CANVAS_HEIGHT * PIXEL_SCALE], fill='white')
                # Redraw grid
                for x in range(0, CANVAS_WIDTH * PIXEL_SCALE, PIXEL_SCALE):
                    draw.line([(x, 0), (x, CANVAS_HEIGHT * PIXEL_SCALE)], fill='#E0E0E0', width=1)
                for y in range(0, CANVAS_HEIGHT * PIXEL_SCALE, PIXEL_SCALE):
                    draw.line([(0, y), (CANVAS_WIDTH * PIXEL_SCALE, y)], fill='#E0E0E0', width=1)
                self._needs_render[guild_id] = True
        except asyncio.TimeoutError:
            logger.error(f"Timeout: Failed to acquire canvas lock for reset for guild {guild_id}")

# Global cache instance
canvas_cache = CanvasCache()
