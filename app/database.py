from contextlib import asynccontextmanager
import asyncpg
from app.config import settings


class Database:
    def __init__(self):
        self.pool: asyncpg.Pool | None = None
    
    async def connect(self):
        if not self.pool:
            self.pool = await asyncpg.create_pool(
                dsn=settings.database_url,
                min_size=2,
                max_size=10
            )
    
    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            self.pool = None
    
    async def fetch_all(self, query: str, *args):
        if not self.pool:
            raise RuntimeError("Database pool is not initialized")
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, *args)
    
    async def fetch_one(self, query: str, *args):
        if not self.pool:
            raise RuntimeError("Database pool is not initialized")
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, *args)
    
    async def execute(self, query: str, *args):
        if not self.pool:
            raise RuntimeError("Database pool is not initialized")
        async with self.pool.acquire() as connection:
            return await connection.execute(query, *args)


db = Database()
