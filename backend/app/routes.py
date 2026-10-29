from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.orm import Session

from app import repository as repo
from app import service
from app.db import get_session
from app.models import Group, User
from app.schemas import BalancesOut, ExpenseCreate, ExpenseOut, GroupDetail, GroupSummary

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


def current_user(session: SessionDep, x_user: Annotated[str | None, Header()] = None) -> User:
    return service.authenticate(session, x_user)


UserDep = Annotated[User, Depends(current_user)]


def member_group(group_id: int, session: SessionDep, user: UserDep) -> Group:
    return service.get_group_for_member(session, group_id, user)


GroupDep = Annotated[Group, Depends(member_group)]


@router.get("/groups", response_model=list[GroupSummary])
def list_groups(session: SessionDep, user: UserDep):
    return [GroupSummary(id=g.id, name=g.name) for g in repo.list_groups_for_user(session, user.id)]


@router.get("/groups/{group_id}", response_model=GroupDetail)
def get_group(group: GroupDep):
    return GroupDetail(id=group.id, name=group.name, members=[m.username for m in group.members])


@router.post(
    "/groups/{group_id}/expenses", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED
)
def create_expense(
    data: ExpenseCreate,
    response: Response,
    session: SessionDep,
    user: UserDep,
    group: GroupDep,
    idempotency_key: Annotated[str | None, Header(max_length=200)] = None,
):
    expense, created = service.create_expense(session, group, user, data, idempotency_key)
    if not created:
        response.status_code = status.HTTP_200_OK
    return expense


@router.get("/groups/{group_id}/expenses", response_model=list[ExpenseOut])
def list_expenses(session: SessionDep, group: GroupDep):
    return service.list_expenses(session, group)


@router.delete("/groups/{group_id}/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, session: SessionDep, user: UserDep, group: GroupDep):
    service.delete_expense(session, group, user, expense_id)


@router.get("/groups/{group_id}/balances", response_model=BalancesOut)
def get_balances(session: SessionDep, group: GroupDep):
    return service.balances(session, group)
