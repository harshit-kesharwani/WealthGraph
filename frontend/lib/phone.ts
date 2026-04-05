/** Normalize for API (backend also normalizes). */
export function digitsOnly(s: string): string {
  return s.replace(/\D/g, "");
}

export function validateIndianMobile(raw: string): string | null {
  const d = digitsOnly(raw);
  if (d.length === 10 && /^[6-9]/.test(d)) return d;
  if (d.length === 12 && d.startsWith("91")) return d.slice(2);
  if (d.length === 11 && d.startsWith("0")) return d.slice(1);
  return null;
}
