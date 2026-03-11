import asyncpg
import asyncio
from config import DATABASE_URL
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.pool = None
        self._blacklist_cache = set()
        self._blacklist_synced = False

    async def connect(self):
        retries = 5
        delay = 2
        while retries > 0:
            try:
                logger.info(f"Connecting to DB...")
                self.pool = await asyncpg.create_pool(
                    DATABASE_URL,
                    min_size=2,
                    max_size=20,
                    statement_cache_size=0
                )
                await self.init_db()
                logger.info("Successfully connected to Database and initialized schema.")
                break
            except Exception as e:
                retries -= 1
                logger.error(f"Failed to connect to Database: {e}. Retries left: {retries}")
                if retries == 0:
                    raise e
                await asyncio.sleep(delay)
                delay *= 2

    async def disconnect(self):
        if self.pool:
            logger.info("Closing database connection pool...")
            await self.pool.close()

    async def init_db(self):
        async with self.pool.acquire() as conn:
            # pixels table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS pixels (
                    guild_id BIGINT NOT NULL,
                    x INT NOT NULL,
                    y INT NOT NULL,
                    color TEXT NOT NULL,
                    is_protected BOOLEAN DEFAULT FALSE,
                    PRIMARY KEY (guild_id, x, y)
                );
            ''')
            
            # safely add is_protected column if it does not exist (for existing databases)
            try:
                await conn.execute('''
                    ALTER TABLE pixels ADD COLUMN IF NOT EXISTS is_protected BOOLEAN DEFAULT FALSE;
                ''')
            except Exception as e:
                logger.warning(f"Could not alter pixels table: {e}")
            
            # pixel_history table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS pixel_history (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT,
                    x INT,
                    y INT,
                    color TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            
            # server_config table for moderation
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS server_config (
                    guild_id BIGINT PRIMARY KEY,
                    log_channel_id BIGINT
                );
            ''')
            
            # blacklist table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS blacklist (
                    user_id BIGINT PRIMARY KEY,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            
            # user_stats table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_stats (
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    pixels_drawn INT DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                );
            ''')
            
            # create index for leaderboard
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_stats_pixels_drawn_guild ON user_stats(guild_id, pixels_drawn DESC);
            ''')
            
            # create index for pixel info lookups
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_pixel_history_guild_xy ON pixel_history(guild_id, x, y);
            ''')
            
            # global_stats table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS global_stats (
                    id INT PRIMARY KEY DEFAULT 1,
                    total_pixels BIGINT DEFAULT 0,
                    CONSTRAINT one_row CHECK (id = 1)
                );
            ''')
            await conn.execute('INSERT INTO global_stats (id, total_pixels) VALUES (1, 0) ON CONFLICT DO NOTHING')

            # factions table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS factions (
                    user_id BIGINT PRIMARY KEY,
                    faction_name VARCHAR(50) NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')

    async def update_pixel(self, guild_id: int, x: int, y: int, color: str, user_id: int):
        async with self.pool.acquire() as conn:
            # Using CTE to reduce DB round-trips
            protected = await conn.fetchval('''
                WITH existing_pixel AS (
                    SELECT is_protected FROM pixels WHERE guild_id = $1 AND x = $2 AND y = $3
                ),
                inserted_pixel AS (
                    INSERT INTO pixels (guild_id, x, y, color)
                    SELECT $1, $2, $3, $4
                    WHERE NOT COALESCE((SELECT is_protected FROM existing_pixel), FALSE)
                    ON CONFLICT (guild_id, x, y) DO UPDATE SET color = EXCLUDED.color
                    WHERE pixels.is_protected = FALSE
                    RETURNING x
                ),
                inserted_history AS (
                    INSERT INTO pixel_history (guild_id, user_id, x, y, color)
                    SELECT $1, $5, $2, $3, $4
                    WHERE EXISTS (SELECT 1 FROM inserted_pixel)
                ),
                updated_stats AS (
                    INSERT INTO user_stats (guild_id, user_id, pixels_drawn)
                    SELECT $1, $5, 1
                    WHERE EXISTS (SELECT 1 FROM inserted_pixel)
                    ON CONFLICT (guild_id, user_id) DO UPDATE SET pixels_drawn = user_stats.pixels_drawn + 1
                )
                SELECT is_protected FROM existing_pixel;
            ''', guild_id, x, y, color, user_id)
            
            if protected:
                raise Exception("This pixel is administratively protected and cannot be overwritten.")
            
            # 4. Increment global pixel count
            return await conn.fetchval('UPDATE global_stats SET total_pixels = total_pixels + 1 WHERE id = 1 RETURNING total_pixels')

    async def get_all_pixels(self, guild_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetch('SELECT x, y, color FROM pixels WHERE guild_id = $1', guild_id)

    async def reset_canvas(self, guild_id: int, hard: bool = False):
        async with self.pool.acquire() as conn:
            if hard:
                await conn.execute('DELETE FROM pixel_history WHERE guild_id = $1', guild_id)
                await conn.execute('DELETE FROM user_stats WHERE guild_id = $1', guild_id)
                await conn.execute('DELETE FROM pixels WHERE guild_id = $1', guild_id)
            else:
                await conn.execute('DELETE FROM pixels WHERE guild_id = $1', guild_id)

    async def get_top_users(self, guild_id: int, limit: int = 10):
        async with self.pool.acquire() as conn:
            return await conn.fetch('SELECT user_id, pixels_drawn FROM user_stats WHERE guild_id = $1 ORDER BY pixels_drawn DESC LIMIT $2', guild_id, limit)

    async def get_pixel_info(self, guild_id: int, x: int, y: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow('''
                SELECT user_id, color, created_at
                FROM pixel_history
                WHERE guild_id = $1 AND x = $2 AND y = $3
                ORDER BY created_at DESC
                LIMIT 1
            ''', guild_id, x, y)

    async def get_user_stats(self, guild_id: int, user_id: int):
        async with self.pool.acquire() as conn:
            # Get stats and rank using window function
            return await conn.fetchrow('''
                WITH RankedUsers AS (
                    SELECT user_id, pixels_drawn, 
                           RANK() OVER (ORDER BY pixels_drawn DESC) as rank
                    FROM user_stats
                    WHERE guild_id = $1
                )
                SELECT pixels_drawn, rank
                FROM RankedUsers
                WHERE user_id = $2
            ''', guild_id, user_id)

    async def set_pixel_protection(self, guild_id: int, x: int, y: int, is_protected: bool):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO pixels (guild_id, x, y, color, is_protected)
                VALUES ($1, $2, $3, 'white', $4)
                ON CONFLICT (guild_id, x, y) DO UPDATE SET is_protected = EXCLUDED.is_protected
            ''', guild_id, x, y, is_protected)

    async def get_pixel_history_stream(self, guild_id: int, limit: int = 100000):
        async with self.pool.acquire() as conn:
            # Order history by oldest to newest, but keep a hard limit so it doesn't crash the bot
            return await conn.fetch('''
                SELECT x, y, color FROM (
                    SELECT id, x, y, color 
                    FROM pixel_history 
                    WHERE guild_id = $1
                    ORDER BY id DESC 
                    LIMIT $2
                ) sub 
                ORDER BY id ASC
            ''', guild_id, limit)

    async def get_last_user_pixel(self, guild_id: int, user_id: int):
        # Fetch the user's most recent pixel placement if it was within the last 5 minutes
        async with self.pool.acquire() as conn:
            return await conn.fetchrow('''
                SELECT id, x, y, color, created_at
                FROM pixel_history
                WHERE guild_id = $1 AND user_id = $2 AND created_at >= NOW() - INTERVAL '5 minutes'
                ORDER BY created_at DESC
                LIMIT 1
            ''', guild_id, user_id)
            
    async def get_previous_pixel_color(self, guild_id: int, x: int, y: int, record_id: int):
        # Find what color the pixel was just before the given record_id
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT color FROM pixel_history
                WHERE guild_id = $1 AND x = $2 AND y = $3 AND id < $4
                ORDER BY id DESC LIMIT 1
            ''', guild_id, x, y, record_id)
            return row['color'] if row else 'white'

    async def undo_pixel(self, guild_id: int, record_id: int, x: int, y: int, previous_color: str, user_id: int):
        async with self.pool.acquire() as conn:
            # Revert the current pixel state, delete the history record, and subtract a stat point safely
            await conn.execute('''
                WITH update_pixel AS (
                    UPDATE pixels SET color = $5 WHERE guild_id = $1 AND x = $3 AND y = $4
                ),
                delete_history AS (
                    DELETE FROM pixel_history WHERE id = $2
                )
                UPDATE user_stats SET pixels_drawn = GREATEST(0, pixels_drawn - 1) WHERE guild_id = $1 AND user_id = $6;
            ''', guild_id, record_id, x, y, previous_color, user_id)

    async def get_log_channel(self, guild_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchval('SELECT log_channel_id FROM server_config WHERE guild_id = $1', guild_id)
            
    async def set_log_channel(self, guild_id: int, channel_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO server_config (guild_id, log_channel_id)
                VALUES ($1, $2)
                ON CONFLICT (guild_id) DO UPDATE SET log_channel_id = EXCLUDED.log_channel_id
            ''', guild_id, channel_id)

    async def get_current_pixel_color(self, guild_id: int, x: int, y: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchval('SELECT color FROM pixels WHERE guild_id = $1 AND x = $2 AND y = $3', guild_id, x, y)

    async def _sync_blacklist_cache(self):
        async with self.pool.acquire() as conn:
            records = await conn.fetch('SELECT user_id FROM blacklist')
            self._blacklist_cache = {r['user_id'] for r in records}
            self._blacklist_synced = True

    async def is_blacklisted(self, user_id: int) -> bool:
        if not self._blacklist_synced:
            await self._sync_blacklist_cache()
        # 0 latency O(1) memory lookup instead of hitting DB every pixel
        return user_id in self._blacklist_cache

    async def ban_user(self, user_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute('INSERT INTO blacklist (user_id) VALUES ($1) ON CONFLICT DO NOTHING', user_id)
            self._blacklist_cache.add(user_id)

    async def unban_user(self, user_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute('DELETE FROM blacklist WHERE user_id = $1', user_id)
            self._blacklist_cache.discard(user_id)
            
    async def join_faction(self, user_id: int, faction_name: str):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO factions (user_id, faction_name) 
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET faction_name = $2
            ''', user_id, faction_name)
            
    async def leave_faction(self, user_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute('DELETE FROM factions WHERE user_id = $1', user_id)

    async def get_user_faction(self, user_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchval('SELECT faction_name FROM factions WHERE user_id = $1', user_id)
            
    async def get_faction_leaderboard(self, guild_id: int = None, limit: int = 10):
        async with self.pool.acquire() as conn:
            if guild_id:
                return await conn.fetch('''
                    SELECT f.faction_name, SUM(s.pixels_drawn) as total_pixels
                    FROM factions f
                    JOIN user_stats s ON f.user_id = s.user_id
                    WHERE s.guild_id = $1
                    GROUP BY f.faction_name
                    ORDER BY total_pixels DESC
                    LIMIT $2
                ''', guild_id, limit)
            else:
                return await conn.fetch('''
                    SELECT f.faction_name, SUM(s.pixels_drawn) as total_pixels
                    FROM factions f
                    JOIN user_stats s ON f.user_id = s.user_id
                    GROUP BY f.faction_name
                    ORDER BY total_pixels DESC
                    LIMIT $1
                ''', limit)
            
    async def get_total_global_pixels(self) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval('SELECT total_pixels FROM global_stats LIMIT 1')

    async def get_user_favorite_color(self, user_id: int, guild_id: int = None):
        async with self.pool.acquire() as conn:
            # Group by color, order by count descending to find their most used color
            if guild_id:
                return await conn.fetchval('''
                    SELECT color FROM pixel_history
                    WHERE user_id = $1 AND guild_id = $2
                    GROUP BY color
                    ORDER BY COUNT(color) DESC
                    LIMIT 1
                ''', user_id, guild_id)
            else:
                return await conn.fetchval('''
                    SELECT color FROM pixel_history
                    WHERE user_id = $1
                    GROUP BY color
                    ORDER BY COUNT(color) DESC
                    LIMIT 1
                ''', user_id)
            
    async def get_color_demographics(self, guild_id: int):
        async with self.pool.acquire() as conn:
            # Tally up the colors currently drawn on the active canvas
            return await conn.fetch('''
                SELECT color, COUNT(color) as count 
                FROM pixels 
                WHERE guild_id = $1
                GROUP BY color 
                ORDER BY count DESC 
                LIMIT 10
            ''', guild_id)
            
    async def batch_update_pixels(self, guild_id: int, pixels_list, user_id: int):
        # High performance insertions using UNNEST array unpacking to CTE
        async with self.pool.acquire() as conn:
            xs = [p[0] for p in pixels_list]
            ys = [p[1] for p in pixels_list]
            colors = [p[2] for p in pixels_list]
            
            updated_count = await conn.fetchval('''
                WITH input_data AS (
                    SELECT * FROM unnest($2::int[], $3::int[], $4::text[]) AS t(new_x, new_y, new_color)
                ),
                inserted_pixels AS (
                    INSERT INTO pixels (guild_id, x, y, color)
                    SELECT $1, new_x, new_y, new_color
                    FROM input_data
                    ON CONFLICT (guild_id, x, y) DO UPDATE SET color = EXCLUDED.color
                    WHERE pixels.is_protected = FALSE
                    RETURNING x, y, color
                ),
                inserted_history AS (
                    INSERT INTO pixel_history (guild_id, x, y, color, user_id)
                    SELECT $1, x, y, color, $5
                    FROM inserted_pixels
                ),
                updated_stats AS (
                    INSERT INTO user_stats (guild_id, user_id, pixels_drawn)
                    SELECT $1, $5, COUNT(*)
                    FROM inserted_pixels
                    HAVING COUNT(*) > 0
                    ON CONFLICT (guild_id, user_id) DO UPDATE SET pixels_drawn = user_stats.pixels_drawn + EXCLUDED.pixels_drawn
                )
                SELECT COUNT(*) FROM inserted_pixels
            ''', guild_id, xs, ys, colors, user_id)
            
            # Increment global stats
            if updated_count and updated_count > 0:
                return await conn.fetchval('UPDATE global_stats SET total_pixels = total_pixels + $1 WHERE id = 1 RETURNING total_pixels', updated_count)
                
    async def get_all_global_pixels(self):
        # Used for full JSON backups
        async with self.pool.acquire() as conn:
            return await conn.fetch('SELECT guild_id, x, y, color FROM pixels')

# Global DB instance
db = Database()
