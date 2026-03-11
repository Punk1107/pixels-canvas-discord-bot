from aiohttp import web
from canvas.renderer import canvas_cache
import logging

logger = logging.getLogger('pixelbot')

async def get_canvas_png(request):
    try:
        buffer = await canvas_cache.get_image_bytes()
        return web.Response(body=buffer.getvalue(), content_type='image/png')
    except Exception as e:
        logger.error(f"Error serving canvas PNG: {e}")
        return web.Response(status=500, text=str(e))

async def start_web_server():
    app = web.Application()
    app.router.add_get('/canvas.png', get_canvas_png)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Run API on port 8080 
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("🌐 Lightweight Web API Server started at http://localhost:8080/canvas.png")
    return runner
