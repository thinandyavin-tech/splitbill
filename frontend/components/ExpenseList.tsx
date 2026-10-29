import type { Expense } from "@/lib/api";
import { formatSatang, parseSatang } from "@/lib/money";

const fmt = (amount: string) => formatSatang(parseSatang(amount) ?? 0);

type Props = { expenses: Expense[]; user: string; onDelete: (id: number) => void };

export function ExpenseList({ expenses, user, onDelete }: Props) {
  return (
    <section className="rounded border p-4">
      <h2 className="mb-2 font-semibold">Expenses</h2>
      {expenses.length === 0 && <p className="text-gray-500">No expenses yet.</p>}
      <ul className="space-y-3">
        {expenses.map((e) => (
          <li key={e.id} className="border-b pb-2 last:border-b-0">
            <div className="flex justify-between gap-2">
              <span className="font-medium">{e.description}</span>
              <span>฿{fmt(e.amount)}</span>
            </div>
            <div className="text-sm text-gray-600">
              Paid by {e.paid_by} · {new Date(e.created_at).toLocaleString("th-TH")}
            </div>
            <div className="text-sm text-gray-600">
              {e.shares.map((s) => `${s.user} ${fmt(s.amount)}`).join(", ")}
            </div>
            {e.paid_by === user && (
              <button className="mt-1 text-sm text-red-700 underline" onClick={() => onDelete(e.id)}>
                Delete
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
