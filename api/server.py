from aiohttp import web
from canvas.renderer import canvas_cache
import logging

logger = logging.getLogger('pixelbot')

async def get_canvas_png(request):
    try:
        guild_id_str = request.match_info.get('guild_id', '')
        if not guild_id_str.isdigit():
            return web.Response(status=400, text="Invalid guild ID")
        
        guild_id = int(guild_id_str)
        buffer = await canvas_cache.get_image_bytes(guild_id)
        
        if buffer.getvalue() == b'':
             return web.Response(status=404, text="Canvas not found or still generating.")
             
        return web.Response(body=buffer.getvalue(), content_type='image/png')
    except Exception as e:
        logger.error(f"Error serving canvas PNG: {e}")
        return web.Response(status=500, text=str(e))

async def start_web_server():
    app = web.Application()
    app.router.add_get('/canvas/{guild_id}.png', get_canvas_png)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Run API on port 8080 
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("🌐 Lightweight Web API Server started at http://localhost:8080/canvas/{guild_id}.png")
    return runner
