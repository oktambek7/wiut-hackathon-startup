import { ApiError } from "./api";
import type { Key } from "./messages";

/** Map an API/network failure to a message key; never blame the contract for a technical failure. */
export function errorKey(e: unknown): Key {
  if (e instanceof ApiError) {
    if (e.status === 0) return "err.network";
    if (e.status === 413) return "err.big";
    if (e.status === 422) return "err.unreadable";
    if (e.status === 429) return "err.busy";
  }
  return "err.generic";
}

export const mbOf = (bytes: number) => Math.round((bytes / 1048576) * 10) / 10;

export function formatDate(iso: string, lang: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  const locale = lang === "ru" ? "ru-RU" : lang === "en" ? "en-GB" : "uz-UZ";
  return d.toLocaleDateString(locale, { weekday: "short", day: "numeric", month: "long", year: "numeric" });
}

export function download(name: string, type: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url; a.download = name; document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export const isoToday = () => new Date().toISOString().slice(0, 10);
