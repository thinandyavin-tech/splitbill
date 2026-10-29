"""Data access. No business rules here: just queries and inserts."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.models import Expense, ExpenseShare, Group, User, group_members


def get_user(session: Session, username: str) -> User | None:
    return session.scalar(select(User).where(User.username == username))


def list_groups_for_user(session: Session, user_id: int) -> list[Group]:
    stmt = (
        select(Group)
        .join(group_members, group_members.c.group_id == Group.id)
        .where(group_members.c.user_id == user_id)
        .order_by(Group.id)
    )
    return list(session.scalars(stmt))


def get_group(session: Session, group_id: int) -> Group | None:
    return session.scalar(
        select(Group).where(Group.id == group_id).options(selectinload(Group.members))
    )


def _expense_query():
    return select(Expense).options(
        selectinload(Expense.paid_by),
        selectinload(Expense.created_by),
        selectinload(Expense.shares).selectinload(ExpenseShare.user),
    )


def get_expense(session: Session, group_id: int, expense_id: int) -> Expense | None:
    return session.scalar(
        _expense_query().where(Expense.group_id == group_id, Expense.id == expense_id)
    )


def get_expense_by_key(session: Session, group_id: int, key: str) -> Expense | None:
    return session.scalar(
        _expense_query().where(Expense.group_id == group_id, Expense.idempotency_key == key)
    )


def list_active_expenses(session: Session, group_id: int) -> list[Expense]:
    stmt = (
        _expense_query()
        .where(Expense.group_id == group_id, Expense.deleted_at.is_(None))
        .order_by(Expense.created_at.desc(), Expense.id.desc())
    )
    return list(session.scalars(stmt))


def insert_expense(
    session: Session,
    *,
    group_id: int,
    description: str,
    paid_by_id: int,
    created_by_id: int,
    amount: Decimal,
    split_type: str,
    idempotency_key: str | None,
    shares: list[tuple[int, Decimal]],
) -> int | None:
    """Insert an expense and its shares.

    Returns the new id, or None if another expense in the group already holds the
    idempotency key. ON CONFLICT DO NOTHING makes PostgreSQL wait for a concurrent
    insert of the same key to commit, so only one of two racing requests gets an id.
    """
    stmt = (
        insert(Expense)
        .values(
            group_id=group_id,
            description=description,
            paid_by_id=paid_by_id,
            created_by_id=created_by_id,
            amount=amount,
            split_type=split_type,
            idempotency_key=idempotency_key,
        )
        .on_conflict_do_nothing(constraint="uq_expenses_group_idempotency_key")
        .returning(Expense.id)
    )
    expense_id = session.scalar(stmt)
    if expense_id is None:
        return None
    session.add_all(
        ExpenseShare(expense_id=expense_id, user_id=user_id, position=i, amount=share)
        for i, (user_id, share) in enumerate(shares)
    )
    session.flush()
    return expense_id


def soft_delete_expense(session: Session, expense: Expense) -> None:
    expense.deleted_at = datetime.now(UTC)


def paid_totals(session: Session, group_id: int) -> dict[int, Decimal]:
    stmt = (
        select(Expense.paid_by_id, func.sum(Expense.amount))
        .where(Expense.group_id == group_id, Expense.deleted_at.is_(None))
        .group_by(Expense.paid_by_id)
    )
    return {user_id: total for user_id, total in session.execute(stmt)}


def owed_totals(session: Session, group_id: int) -> dict[int, Decimal]:
    stmt = (
        select(ExpenseShare.user_id, func.sum(ExpenseShare.amount))
        .join(Expense, Expense.id == ExpenseShare.expense_id)
        .where(Expense.group_id == group_id, Expense.deleted_at.is_(None))
        .group_by(ExpenseShare.user_id)
    )
    return {user_id: total for user_id, total in session.execute(stmt)}
