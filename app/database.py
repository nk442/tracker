"""
Настройка подключения к базе данных через SQLAlchemy
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.models.database import Base


class Database:
    """Класс для управления подключением к базе данных через SQLAlchemy"""
    
    def __init__(self):
        self.engine = None
        self.async_session_maker: async_sessionmaker[AsyncSession] | None = None
    
    async def connect(self):
        """Создает async engine и session maker"""
        if not self.engine:
            # Преобразуем postgresql:// в postgresql+asyncpg:// для asyncpg
            database_url = settings.database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
            
            self.engine = create_async_engine(
                database_url,
                echo=False,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True
            )
            
            self.async_session_maker = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
    
    async def disconnect(self):
        """Закрывает engine"""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.async_session_maker = None
    


db = Database()
