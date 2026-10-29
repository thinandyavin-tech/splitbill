from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Amounts stay strings at the API boundary; app.money turns them into integer satang.
# strict=True stops pydantic from coercing JSON numbers like 10.5 into "10.5".
AmountStr = Annotated[str, Field(strict=True)]


class EqualSplit(BaseModel):
    type: Literal["equal"]
    members: list[str] = Field(min_length=1)


class ExactSplit(BaseModel):
    type: Literal["exact"]
    shares: dict[str, AmountStr] = Field(min_length=1)


class ExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    paid_by: str
    amount: AmountStr
    split: EqualSplit | ExactSplit = Field(discriminator="type")


class GroupSummary(BaseModel):
    id: int
    name: str


class GroupDetail(GroupSummary):
    members: list[str]


class ShareOut(BaseModel):
    user: str
    amount: str


class ExpenseOut(BaseModel):
    id: int
    group_id: int
    description: str
    paid_by: str
    created_by: str
    amount: str
    split_type: str
    shares: list[ShareOut]
    created_at: datetime
    deleted: bool


class BalanceOut(BaseModel):
    user: str
    balance: str


class BalancesOut(BaseModel):
    group_id: int
    balances: list[BalanceOut]
