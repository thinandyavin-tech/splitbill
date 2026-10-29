"use client";

import { useCallback, useEffect, useState } from "react";
import { BalanceList } from "@/components/BalanceList";
import { ExpenseForm } from "@/components/ExpenseForm";
import { ExpenseList } from "@/components/ExpenseList";
import { api, ApiError, type Balance, type Expense, type Group, type GroupDetail } from "@/lib/api";

// There is no /users endpoint in the brief, so the seeded users are listed here.
const USERS = ["alice", "bob", "carol", "dan"];

function message(err: unknown) {
  return err instanceof ApiError ? err.message : "Something went wrong.";
}

export default function Home() {
  const [user, setUser] = useState(USERS[0]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [groupId, setGroupId] = useState<number | null>(null);
  const [group, setGroup] = useState<GroupDetail | null>(null);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [balances, setBalances] = useState<Balance[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    setGroups([]);
    setGroupId(null);
    api
      .groups(user)
      .then((gs) => {
        setGroups(gs);
        setGroupId(gs[0]?.id ?? null);
      })
      .catch((e) => setError(message(e)));
  }, [user]);

  const refresh = useCallback(async () => {
    if (groupId === null) {
      setGroup(null);
      return;
    }
    try {
      const [g, ex, bal] = await Promise.all([
        api.group(user, groupId),
        api.expenses(user, groupId),
        api.balances(user, groupId),
      ]);
      setGroup(g);
      setExpenses(ex);
      setBalances(bal);
    } catch (e) {
      setError(message(e));
    }
  }, [user, groupId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleDelete(expenseId: number) {
    if (groupId === null) return;
    setError(null);
    try {
      await api.deleteExpense(user, groupId, expenseId);
      await refresh();
    } catch (e) {
      setError(message(e));
    }
  }

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-6">
      <h1 className="text-2xl font-bold">SplitBill</h1>

      <div className="flex flex-wrap gap-4">
        <label className="flex flex-col text-sm">
          User
          <select className="rounded border p-2" value={user} onChange={(e) => setUser(e.target.value)}>
            {USERS.map((u) => (
              <option key={u}>{u}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col text-sm">
          Group
          <select
            className="rounded border p-2"
            value={groupId ?? ""}
            onChange={(e) => setGroupId(Number(e.target.value))}
          >
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && (
        <p role="alert" className="rounded border border-red-300 bg-red-50 p-3 text-red-800">
          {error}
        </p>
      )}

      {group && (
        <div className="grid gap-6 md:grid-cols-2">
          <ExpenseForm
            key={`${user}-${group.id}`}
            user={user}
            group={group}
            onCreated={() => {
              setError(null);
              refresh();
            }}
          />
          <div className="space-y-6">
            <BalanceList balances={balances} />
            <ExpenseList expenses={expenses} user={user} onDelete={handleDelete} />
          </div>
        </div>
      )}
    </main>
  );
}
