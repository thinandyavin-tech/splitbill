"use client";

import { useState } from "react";
import { api, ApiError, type GroupDetail, type Split } from "@/lib/api";
import { formatSatang, parseSatang, splitEqual, toAmountString } from "@/lib/money";

type Props = { user: string; group: GroupDetail; onCreated: () => void };

export function ExpenseForm({ user, group, onCreated }: Props) {
  const members = group.members;
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [paidBy, setPaidBy] = useState(members.includes(user) ? user : members[0]);
  const [splitType, setSplitType] = useState<"equal" | "exact">("equal");
  const [selected, setSelected] = useState<string[]>(members);
  const [exact, setExact] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // One key per draft: retries and double-clicks of the same expense reuse it, so the
  // backend records it only once. A fresh key is made after a successful save.
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());

  const total = parseSatang(amount.trim());
  const amountInvalid = amount.trim() !== "" && (total === null || total === 0);

  // Equal split keeps the group's member order, which decides who gets leftover satang.
  const equalMembers = members.filter((m) => selected.includes(m));
  const equalShares = total && equalMembers.length > 0 ? splitEqual(total, equalMembers) : null;

  const exactShares = members.map((m) => {
    const raw = (exact[m] ?? "").trim();
    return { member: m, raw, satang: raw === "" ? 0 : parseSatang(raw) };
  });
  const exactInvalid = exactShares.some((s) => s.satang === null);
  const allocated = exactShares.reduce((sum, s) => sum + (s.satang ?? 0), 0);
  const unallocated = total === null ? null : total - allocated;

  const canSubmit =
    description.trim() !== "" &&
    !!total &&
    !submitting &&
    (splitType === "equal"
      ? equalMembers.length > 0
      : !exactInvalid && unallocated === 0 && exactShares.some((s) => s.satang));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit || !total) return;
    const split: Split =
      splitType === "equal"
        ? { type: "equal", members: equalMembers }
        : {
            type: "exact",
            shares: Object.fromEntries(
              exactShares.filter((s) => s.satang).map((s) => [s.member, toAmountString(s.satang!)]),
            ),
          };
    setSubmitting(true);
    setError(null);
    try {
      await api.createExpense(
        user,
        group.id,
        { description: description.trim(), paid_by: paidBy, amount: toAmountString(total), split },
        idempotencyKey,
      );
      setDescription("");
      setAmount("");
      setExact({});
      setIdempotencyKey(crypto.randomUUID());
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded border p-4">
      <h2 className="font-semibold">Add expense to {group.name}</h2>

      <label className="flex flex-col text-sm">
        Description
        <input
          className="rounded border p-2"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={200}
        />
      </label>

      <label className="flex flex-col text-sm">
        Amount (THB)
        <input
          className="rounded border p-2"
          inputMode="decimal"
          placeholder="1000.00"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        {amountInvalid && (
          <span className="text-red-700">Enter an amount above 0 with at most 2 decimal places.</span>
        )}
      </label>

      <label className="flex flex-col text-sm">
        Paid by
        <select className="rounded border p-2" value={paidBy} onChange={(e) => setPaidBy(e.target.value)}>
          {members.map((m) => (
            <option key={m}>{m}</option>
          ))}
        </select>
      </label>

      <fieldset className="text-sm">
        <legend>Split</legend>
        {(["equal", "exact"] as const).map((t) => (
          <label key={t} className="mr-4">
            <input
              type="radio"
              name="split"
              className="mr-1"
              checked={splitType === t}
              onChange={() => setSplitType(t)}
            />
            {t === "equal" ? "Equally" : "Exact amounts"}
          </label>
        ))}
      </fieldset>

      <ul className="space-y-1 text-sm">
        {members.map((m) => (
          <li key={m} className="flex items-center justify-between gap-2">
            {splitType === "equal" ? (
              <>
                <label>
                  <input
                    type="checkbox"
                    className="mr-1"
                    checked={selected.includes(m)}
                    onChange={(e) =>
                      setSelected(e.target.checked ? [...selected, m] : selected.filter((s) => s !== m))
                    }
                  />
                  {m}
                </label>
                <span>{equalShares?.has(m) ? `฿${formatSatang(equalShares.get(m)!)}` : "–"}</span>
              </>
            ) : (
              <>
                <span>{m}</span>
                <input
                  aria-label={`Share for ${m}`}
                  className={`w-32 rounded border p-1 text-right ${
                    exactShares.find((s) => s.member === m)?.satang === null ? "border-red-500" : ""
                  }`}
                  inputMode="decimal"
                  placeholder="0.00"
                  value={exact[m] ?? ""}
                  onChange={(e) => setExact({ ...exact, [m]: e.target.value })}
                />
              </>
            )}
          </li>
        ))}
      </ul>

      {splitType === "exact" && unallocated !== null && (
        <p className={`text-sm ${unallocated === 0 ? "text-green-700" : "text-red-700"}`}>
          {unallocated === 0
            ? "Shares add up to the total."
            : unallocated > 0
              ? `฿${formatSatang(unallocated)} left to allocate`
              : `฿${formatSatang(-unallocated)} over the total`}
        </p>
      )}

      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={!canSubmit}
        className="rounded bg-blue-600 px-4 py-2 text-white disabled:cursor-not-allowed disabled:bg-gray-400"
      >
        {submitting ? "Saving…" : "Add expense"}
      </button>
    </form>
  );
}
