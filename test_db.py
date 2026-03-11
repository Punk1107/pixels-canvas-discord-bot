import asyncio
import asyncpg

async def main():
    try:
        conn = await asyncpg.connect(user="postgres", password="your_password", database="postgres", host="localhost")
        print("Success: your_password")
        await conn.close()
    except Exception as e:
        print(f"Failed: {e}")

asyncio.run(main())
