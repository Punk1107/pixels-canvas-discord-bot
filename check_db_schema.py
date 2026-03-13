import asyncpg
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def check_constraints():
    conn = await asyncpg.connect(DATABASE_URL)
    
    print("--- Table: pixels ---")
    rows = await conn.fetch('''
        SELECT conname, pg_get_constraintdef(c.oid)
        FROM pg_constraint c
        JOIN pg_namespace n ON n.oid = c.connamespace
        WHERE contype IN ('p', 'u') AND conrelid = 'pixels'::regclass;
    ''')
    for row in rows:
        print(f"Constraint: {row['conname']}, Definition: {row['pg_get_constraintdef']}")

    print("\n--- Indexes on pixels ---")
    rows = await conn.fetch('''
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'pixels';
    ''')
    for row in rows:
        print(f"Index: {row['indexname']}, Definition: {row['indexdef']}")

    print("\n--- Columns in pixels ---")
    rows = await conn.fetch('''
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'pixels'
        ORDER BY ordinal_position;
    ''')
    for row in rows:
        print(f"Column: {row['column_name']}, Type: {row['data_type']}, Nullable: {row['is_nullable']}")

    await conn.close()

if __name__ == '__main__':
    asyncio.run(check_constraints())
