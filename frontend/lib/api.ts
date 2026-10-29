const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Group = { id: number; name: string };
export type GroupDetail = Group & { members: string[] };
export type Share = { user: string; amount: string };
export type Expense = {
  id: number;
  description: string;
  paid_by: string;
  created_by: string;
  amount: string;
  split_type: "equal" | "exact";
  shares: Share[];
  created_at: string;
};
export type Balance = { user: string; balance: string };
export type Split =
  | { type: "equal"; members: string[] }
  | { type: "exact"; shares: Record<string, string> };
export type NewExpense = { description: string; paid_by: string; amount: string; split: Split };

// Plain-language text for the backend's error codes.
const MESSAGES: Record<string, string> = {
  shares_mismatch: "The shares do not add up to the total.",
  not_group_member: "Not a member of this group.",
  group_not_found: "This group does not exist or you are not a member of it.",
  expense_not_found: "This expense no longer exists. It may have been deleted already.",
  not_payer: "Only the person who paid can delete this expense.",
  unauthenticated: "Please choose a user first.",
  duplicate_member: "A member is listed twice in the split.",
};

export class ApiError extends Error {}

async function request<T>(user: string, path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", "X-User": user, ...init.headers },
    });
  } catch {
    throw new ApiError("Cannot reach the server. Check that the API is running.");
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const error = body?.error;
    // Validation errors already carry a readable message (e.g. "amount must have at most 2 decimal places").
    throw new ApiError(MESSAGES[error?.code] ?? error?.message ?? `Request failed (${res.status}).`);
  }
  return body as T;
}

export const api = {
  groups: (user: string) => request<Group[]>(user, "/groups"),
  group: (user: string, id: number) => request<GroupDetail>(user, `/groups/${id}`),
  expenses: (user: string, id: number) => request<Expense[]>(user, `/groups/${id}/expenses`),
  balances: (user: string, id: number) =>
    request<{ balances: Balance[] }>(user, `/groups/${id}/balances`).then((r) => r.balances),
  createExpense: (user: string, id: number, data: NewExpense, idempotencyKey: string) =>
    request<Expense>(user, `/groups/${id}/expenses`, {
      method: "POST",
      body: JSON.stringify(data),
      headers: { "Idempotency-Key": idempotencyKey },
    }),
  deleteExpense: (user: string, groupId: number, expenseId: number) =>
    request<void>(user, `/groups/${groupId}/expenses/${expenseId}`, { method: "DELETE" }),
};
