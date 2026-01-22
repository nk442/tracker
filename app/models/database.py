"""
SQLAlchemy модели для базы данных
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, 
    DateTime, JSON, UniqueConstraint, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Offer(Base):
    """Модель оффера"""
    __tablename__ = "offers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # Связи
    campaigns = relationship("Campaign", back_populates="offer", cascade="all, delete-orphan")


class Campaign(Base):
    """Модель кампании"""
    __tablename__ = "campaigns"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    offer_url = Column(Text, nullable=False)
    offer_id = Column(Integer, ForeignKey("offers.id"), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # Связи
    offer = relationship("Offer", back_populates="campaigns")
    events = relationship("Event", back_populates="campaign", cascade="all, delete-orphan")
    domain_emails = relationship("CampaignDomainEmails", back_populates="campaign", cascade="all, delete-orphan")


class Event(Base):
    """Модель события"""
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    domain = Column(String(255), nullable=False, index=True)
    ip = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    extra_params = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    
    # Связи
    campaign = relationship("Campaign", back_populates="events")
    
    __table_args__ = (
        Index("idx_events_campaign", "campaign_id"),
        Index("idx_events_email", "email"),
        Index("idx_events_domain", "domain"),
        Index("idx_events_created_at", "created_at"),
    )


class CampaignDomainEmails(Base):
    """Модель для хранения количества отправленных писем по доменам"""
    __tablename__ = "campaign_domain_emails"
    
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    domain = Column(String(255), nullable=False, index=True)
    emails_sent = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Связи
    campaign = relationship("Campaign", back_populates="domain_emails")
    
    __table_args__ = (
        UniqueConstraint("campaign_id", "domain", name="campaign_domain_emails_campaign_id_domain_key"),
        Index("idx_campaign_domain_emails_campaign", "campaign_id"),
        Index("idx_campaign_domain_emails_domain", "domain"),
    )
