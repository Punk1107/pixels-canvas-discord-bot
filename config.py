import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_NAME = os.getenv("DB_NAME", "pixelbot")
DATABASE_URL = os.getenv("DATABASE_URL", f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

CANVAS_WIDTH = int(os.getenv("CANVAS_WIDTH", "50"))
CANVAS_HEIGHT = int(os.getenv("CANVAS_HEIGHT", "50"))
PIXEL_SCALE = int(os.getenv("PIXEL_SCALE", "10"))
