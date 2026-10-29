"use client";

import { useEffect, useState } from "react";
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
  // Bumped after a create or delete to reload the selected group.
  const [version, setVersion] = useState(0);

  // Clear the selection in the same render as the switch, so the old group is never
  // requested as the new user (which would show a false "not a member" error).
  function selectUser(u: string) {
    setUser(u);
    setGroups([]);
    selectGroup(null);
  }

  function selectGroup(id: number | null) {
    setGroupId(id);
    setGroup(null);
    setError(null);
  }

  useEffect(() => {
    let stale = false;
    api
      .groups(user)
      .then((gs) => {
        if (stale) return;
        setGroups(gs);
        selectGroup(gs[0]?.id ?? null);
      })
      .catch((e) => !stale && setError(message(e)));
    return () => {
      stale = true;
    };
  }, [user]);

  useEffect(() => {
    if (groupId === null) return;
    // Ignore responses that arrive after the user or group has changed again.
    let stale = false;
    Promise.all([api.group(user, groupId), api.expenses(user, groupId), api.balances(user, groupId)])
      .then(([g, ex, bal]) => {
        if (stale) return;
        setGroup(g);
        setExpenses(ex);
        setBalances(bal);
      })
      .catch((e) => !stale && setError(message(e)));
    return () => {
      stale = true;
    };
  }, [user, groupId, version]);

  const reload = () => setVersion((v) => v + 1);

  async function handleDelete(expenseId: number) {
    if (groupId === null) return;
    setError(null);
    try {
      await api.deleteExpense(user, groupId, expenseId);
      reload();
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
          <select className="rounded border p-2" value={user} onChange={(e) => selectUser(e.target.value)}>
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
            onChange={(e) => selectGroup(Number(e.target.value))}
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
              reload();
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
