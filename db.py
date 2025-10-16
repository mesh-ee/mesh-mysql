from sqlalchemy import (
    create_engine, Column, Integer, String, BigInteger, Float, DECIMAL, Boolean, Text,
    ForeignKey, Index, TIMESTAMP, func
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Node(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    short_id = Column(String(255), unique=True, nullable=True)
    long_id = Column(BigInteger, unique=True, nullable=True)
    long_name = Column(String(255), nullable=True)
    short_name = Column(String(64), nullable=True)
    role = Column(String(255), nullable=True)
    hw_model = Column(String(255), nullable=True)
    is_unmessagable = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    messages_sent = relationship(
        "Message",
        foreign_keys="Message.from_node_id",
        back_populates="from_node",
        cascade="all, delete-orphan"
    )
    telemetry = relationship(
        "Telemetry",
        back_populates="node",
        cascade="all, delete-orphan"
    )
    traceroutes_from = relationship(
        "Traceroute",
        foreign_keys="Traceroute.from_node_id",
        back_populates="from_node",
        cascade="all, delete-orphan"
    )
    traceroutes_to = relationship(
        "Traceroute",
        foreign_keys="Traceroute.to_node_id",
        back_populates="to_node",
        cascade="all, delete-orphan"
    )

    positions = relationship(
        "Position",
        back_populates="node",
        cascade="all, delete-orphan"
    )


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    node_id = Column(Integer, ForeignKey("nodes.id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    longitude = Column(DECIMAL(10, 7), nullable=True)
    latitude = Column(DECIMAL(10, 7), nullable=True)
    altitude = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    node = relationship("Node", back_populates="positions")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_node_id = Column(Integer, ForeignKey("nodes.id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=True)
    rx_rssi = Column(Integer, nullable=True)
    rx_snr = Column(Integer, nullable=True)
    rx_time = Column(BigInteger, nullable=True)
    via_mqtt = Column(Boolean, default=False)

    from_node = relationship("Node", foreign_keys=[from_node_id], back_populates="messages_sent")

    __table_args__ = (
        Index("idx_from_time", "from_node_id", "rx_time"),
    )


class Telemetry(Base):
    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    node_id = Column(Integer, ForeignKey("nodes.id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    battery = Column(Integer, nullable=True)
    uptime = Column(BigInteger, nullable=True)
    voltage = Column(DECIMAL(5, 2), nullable=True)
    channel_util = Column(DECIMAL(5, 2), nullable=True)
    air_util_tx = Column(DECIMAL(5, 2), nullable=True)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    pressure = Column(Float, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    node = relationship("Node", back_populates="telemetry")

    __table_args__ = (
        Index("idx_node_time", "node_id", "created_at"),
    )

class Traceroute(Base):
    __tablename__ = "traceroutes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    from_node_id = Column(Integer, ForeignKey("nodes.id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    to_node_id = Column(Integer, ForeignKey("nodes.id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)

    hops = Column(Text, nullable=True) 
    via_mqtt = Column(Boolean, default=False)

    from_node = relationship("Node", foreign_keys=[from_node_id], back_populates="traceroutes_from")
    to_node = relationship("Node", foreign_keys=[to_node_id], back_populates="traceroutes_to")

def init_db():
    Base.metadata.create_all(bind=engine)
