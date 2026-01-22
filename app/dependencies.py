"""
Dependencies для FastAPI
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import db


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency для получения сессии базы данных.
    Автоматически закрывает сессию после использования.
    """
    if not db.async_session_maker:
        raise RuntimeError("Database session maker is not initialized")
    
    async with db.async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
