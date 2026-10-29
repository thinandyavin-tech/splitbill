// Money is handled as integer satang (1 THB = 100 satang) so no floating-point
// arithmetic ever touches an amount. Mirrors backend/app/money.py.

const AMOUNT_RE = /^\d+(\.\d{1,2})?$/;
const MAX_SATANG = 10 ** 12 - 1; // NUMERIC(12,2)

/** Parse "1000.5" -> 100050. Returns null for anything the backend would reject. */
export function parseSatang(input: string): number | null {
  if (!AMOUNT_RE.test(input)) return null;
  const [whole, frac = ""] = input.split(".");
  const satang = Number(whole) * 100 + Number(frac.padEnd(2, "0"));
  return satang <= MAX_SATANG ? satang : null;
}

/** Equal shares; leftover satang go one at a time to members in the order listed. */
export function splitEqual(total: number, members: string[]): Map<string, number> {
  const base = Math.floor(total / members.length);
  const remainder = total % members.length;
  return new Map(members.map((m, i) => [m, base + (i < remainder ? 1 : 0)]));
}

/** 100000 -> "1,000.00", -3333 -> "-33.33" */
export function formatSatang(satang: number): string {
  const sign = satang < 0 ? "-" : "";
  const abs = Math.abs(satang);
  const whole = Math.floor(abs / 100)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const frac = (abs % 100).toString().padStart(2, "0");
  return `${sign}${whole}.${frac}`;
}

/** Wire format for the API: 100050 -> "1000.50" */
export function toAmountString(satang: number): string {
  return formatSatang(satang).replaceAll(",", "");
}
