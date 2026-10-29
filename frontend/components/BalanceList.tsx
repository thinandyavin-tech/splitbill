import type { Balance } from "@/lib/api";
import { formatSatang, parseSatang } from "@/lib/money";

function toSatang(balance: string): number {
  const negative = balance.startsWith("-");
  const satang = parseSatang(negative ? balance.slice(1) : balance) ?? 0;
  return negative ? -satang : satang;
}

export function BalanceList({ balances }: { balances: Balance[] }) {
  return (
    <section className="rounded border p-4">
      <h2 className="mb-2 font-semibold">Balances</h2>
      <ul className="space-y-1">
        {balances.map((b) => {
          const satang = toSatang(b.balance);
          return (
            <li key={b.user} className="flex justify-between">
              <span>{b.user}</span>
              {satang > 0 && <span className="text-green-700">is owed ฿{formatSatang(satang)}</span>}
              {satang < 0 && <span className="text-red-700">owes ฿{formatSatang(-satang)}</span>}
              {satang === 0 && <span className="text-gray-500">settled up</span>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
