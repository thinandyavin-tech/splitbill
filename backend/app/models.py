from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


group_members = Table(
    "group_members",
    Base.metadata,
    Column("group_id", ForeignKey("groups.id"), primary_key=True),
    Column("user_id", ForeignKey("users.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    members: Mapped[list[User]] = relationship(secondary=group_members, order_by=User.id)


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        UniqueConstraint("group_id", "idempotency_key", name="uq_expenses_group_idempotency_key"),
        CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        CheckConstraint("split_type IN ('equal', 'exact')", name="ck_expenses_split_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    description: Mapped[str] = mapped_column(String(200))
    paid_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    split_type: Mapped[str] = mapped_column(String(10))
    idempotency_key: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    paid_by: Mapped[User] = relationship(foreign_keys=[paid_by_id])
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])
    shares: Mapped[list["ExpenseShare"]] = relationship(order_by="ExpenseShare.position")


class ExpenseShare(Base):
    __tablename__ = "expense_shares"
    __table_args__ = (CheckConstraint("amount >= 0", name="ck_expense_shares_amount"),)

    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    # Preserves the order members were listed in, which decides who got the leftover satang.
    position: Mapped[int] = mapped_column(Integer)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    user: Mapped[User] = relationship()
