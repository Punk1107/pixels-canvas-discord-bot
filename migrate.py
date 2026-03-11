import asyncpg
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_NAME = os.getenv("DB_NAME", "pixelbot")
DATABASE_URL = os.getenv("DATABASE_URL", f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

async def run_migration():
    conn = await asyncpg.connect(DATABASE_URL)
    print("Dropping tables to allow schema update...")
    await conn.execute("DROP TABLE IF EXISTS pixels")
    await conn.execute("DROP TABLE IF EXISTS pixel_history")
    await conn.execute("DROP TABLE IF EXISTS user_stats")
    print("Tables dropped.")
    await conn.close()

if __name__ == '__main__':
    asyncio.run(run_migration())
