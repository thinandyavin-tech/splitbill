"""Business rules. Routers call these; these call app.repository for data."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app import repository as repo
from app.errors import Forbidden, NotFound, Unauthenticated, ValidationFailed
from app.models import Expense, Group, User
from app.money import format_amount, parse_satang, split_equal, to_decimal, to_satang
from app.schemas import (
    BalanceOut,
    BalancesOut,
    EqualSplit,
    ExactSplit,
    ExpenseCreate,
    ExpenseOut,
    ShareOut,
)


def authenticate(session: Session, username: str | None) -> User:
    if not username:
        raise Unauthenticated("Missing X-User header")
    user = repo.get_user(session, username)
    if user is None:
        raise Unauthenticated(f"Unknown user '{username}'")
    return user


def get_group_for_member(session: Session, group_id: int, user: User) -> Group:
    """Load a group the user belongs to.

    Non-members get the same 404 as a group that does not exist, so the API does not
    reveal which group ids exist (see README).
    """
    group = repo.get_group(session, group_id)
    if group is None or user.id not in {m.id for m in group.members}:
        raise NotFound(f"Group {group_id} not found", code="group_not_found")
    return group


def compute_shares(total: int, split: EqualSplit | ExactSplit) -> list[tuple[str, int]]:
    """Return (username, satang) pairs in the order the client listed them."""
    if isinstance(split, EqualSplit):
        if len(set(split.members)) != len(split.members):
            raise ValidationFailed("A member is listed twice in the split", code="duplicate_member")
        return list(split_equal(total, split.members).items())

    shares = [
        (user, parse_satang(value, f"share for {user}", allow_zero=True))
        for user, value in split.shares.items()
    ]
    allocated = sum(s for _, s in shares)
    if allocated != total:
        raise ValidationFailed(
            f"The shares add up to {format_amount(allocated)} "
            f"but the amount is {format_amount(total)}",
            code="shares_mismatch",
        )
    return shares


def create_expense(
    session: Session,
    group: Group,
    user: User,
    data: ExpenseCreate,
    idempotency_key: str | None,
) -> tuple[ExpenseOut, bool]:
    """Record an expense. Returns (expense, created); created is False on an idempotent replay."""
    if idempotency_key:
        existing = repo.get_expense_by_key(session, group.id, idempotency_key)
        if existing is not None:
            return expense_out(existing), False

    total = parse_satang(data.amount, "amount")
    members = {m.username: m for m in group.members}
    if data.paid_by not in members:
        raise ValidationFailed(
            f"Payer '{data.paid_by}' is not a member of this group", code="not_group_member"
        )
    shares = compute_shares(total, data.split)
    outsiders = [u for u, _ in shares if u not in members]
    if outsiders:
        raise ValidationFailed(
            f"Not a member of this group: {', '.join(outsiders)}", code="not_group_member"
        )

    expense_id = repo.insert_expense(
        session,
        group_id=group.id,
        description=data.description,
        paid_by_id=members[data.paid_by].id,
        created_by_id=user.id,
        amount=to_decimal(total),
        split_type=data.split.type,
        idempotency_key=idempotency_key,
        shares=[(members[u].id, to_decimal(s)) for u, s in shares],
    )
    session.commit()
    if expense_id is None:
        # A concurrent request with the same key won the race; return its expense.
        return expense_out(repo.get_expense_by_key(session, group.id, idempotency_key)), False
    return expense_out(repo.get_expense(session, group.id, expense_id)), True


def list_expenses(session: Session, group: Group) -> list[ExpenseOut]:
    return [expense_out(e) for e in repo.list_active_expenses(session, group.id)]


def delete_expense(session: Session, group: Group, user: User, expense_id: int) -> None:
    expense = repo.get_expense(session, group.id, expense_id)
    if expense is None or expense.deleted_at is not None:
        raise NotFound(f"Expense {expense_id} not found", code="expense_not_found")
    if expense.paid_by_id != user.id:
        raise Forbidden("Only the payer can delete this expense", code="not_payer")
    repo.soft_delete_expense(session, expense)
    session.commit()


def member_balances(session: Session, group: Group) -> list[tuple[str, int]]:
    """Net satang per member: what they paid minus their shares. Sums to zero by construction."""
    paid = repo.paid_totals(session, group.id)
    owed = repo.owed_totals(session, group.id)
    zero = Decimal(0)
    return [
        (m.username, to_satang(paid.get(m.id, zero) - owed.get(m.id, zero))) for m in group.members
    ]


def balances(session: Session, group: Group) -> BalancesOut:
    return BalancesOut(
        group_id=group.id,
        balances=[
            BalanceOut(user=u, balance=format_amount(b)) for u, b in member_balances(session, group)
        ],
    )


def expense_out(expense: Expense) -> ExpenseOut:
    return ExpenseOut(
        id=expense.id,
        group_id=expense.group_id,
        description=expense.description,
        paid_by=expense.paid_by.username,
        created_by=expense.created_by.username,
        amount=str(expense.amount),
        split_type=expense.split_type,
        shares=[ShareOut(user=s.user.username, amount=str(s.amount)) for s in expense.shares],
        created_at=expense.created_at,
        deleted=expense.deleted_at is not None,
    )
