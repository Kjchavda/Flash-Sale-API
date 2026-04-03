from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
import uuid
import enum
from datetime import datetime
from backend.database import Base 


# ── Enums ────────────────────────────────────────────────────────────────────

class TicketStatus(enum.Enum):
    AVAILABLE = "available"
    LOCKED    = "locked"
    SOLD      = "sold"

class OrderStatus(enum.Enum):
    PENDING = "pending"
    PAID    = "paid"
    FAILED  = "failed"


# ── Tables ───────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    user_id       : Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email         : Mapped[str]       = mapped_column(String(255), unique=True, nullable=False)
    password_hash : Mapped[str]       = mapped_column(String(255), nullable=False)
    created_at    : Mapped[datetime]  = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    orders         : Mapped[list["Order"]]  = relationship("Order", back_populates="user")
    locked_tickets : Mapped[list["Ticket"]] = relationship("Ticket", back_populates="locked_by_user")


class Venue(Base):
    __tablename__ = "venues"

    venue_id     : Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name         : Mapped[str]       = mapped_column(String(255), nullable=False)
    address      : Mapped[str]       = mapped_column(String(500), nullable=False)
    city         : Mapped[str]       = mapped_column(String(100), nullable=False)
    max_capacity : Mapped[int]       = mapped_column(Integer, nullable=False)

    # Relationships
    events : Mapped[list["Event"]] = relationship("Event", back_populates="venue")


class Event(Base):
    __tablename__ = "events"

    event_id        : Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id        : Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), ForeignKey("venues.venue_id"), nullable=False)
    title           : Mapped[str]              = mapped_column(String(255), nullable=False)
    description     : Mapped[Optional[str]]    = mapped_column(Text, nullable=True)
    sale_start_time : Mapped[datetime]         = mapped_column(DateTime, nullable=False)

    # Relationships
    venue        : Mapped["Venue"]             = relationship("Venue", back_populates="events")
    ticket_tiers : Mapped[list["TicketTier"]] = relationship("TicketTier", back_populates="event")


class TicketTier(Base):
    __tablename__ = "ticket_tiers"

    tier_id         : Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id        : Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.event_id"), nullable=False)
    tier_name       : Mapped[str]       = mapped_column(String(100), nullable=False)
    price           : Mapped[float]     = mapped_column(Numeric(10, 2), nullable=False)
    total_allocated : Mapped[int]       = mapped_column(Integer, nullable=False)

    # Relationships
    event   : Mapped["Event"]          = relationship("Event", back_populates="ticket_tiers")
    tickets : Mapped[list["Ticket"]]   = relationship("Ticket", back_populates="tier")


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id    : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tier_id      : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), ForeignKey("ticket_tiers.tier_id"), nullable=False)
    locked_by    : Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    status       : Mapped[TicketStatus]        = mapped_column(Enum(TicketStatus), nullable=False, default=TicketStatus.AVAILABLE)
    locked_until : Mapped[Optional[datetime]]  = mapped_column(DateTime, nullable=True)

    # Relationships
    tier           : Mapped["TicketTier"]         = relationship("TicketTier", back_populates="tickets")
    locked_by_user : Mapped[Optional["User"]]     = relationship("User", back_populates="locked_tickets")
    order_item     : Mapped[Optional["OrderItem"]] = relationship("OrderItem", back_populates="ticket", uselist=False)


class Order(Base):
    __tablename__ = "orders"

    order_id     : Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      : Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    total_amount : Mapped[float]       = mapped_column(Numeric(10, 2), nullable=False)
    status       : Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    created_at   : Mapped[datetime]    = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user  : Mapped["User"]             = relationship("User", back_populates="orders")
    items : Mapped[list["OrderItem"]]  = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    item_id    : Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id   : Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.order_id"), nullable=False)
    ticket_id  : Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.ticket_id"), nullable=False)
    price_paid : Mapped[float]     = mapped_column(Numeric(10, 2), nullable=False)

    # Relationships
    order  : Mapped["Order"]  = relationship("Order", back_populates="items")
    ticket : Mapped["Ticket"] = relationship("Ticket", back_populates="order_item")