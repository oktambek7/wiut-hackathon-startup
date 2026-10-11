import type { Catalogue, CheckResponse, Clock, Lang, Letter, Plan, View } from "./types";

export const API = (process.env.NEXT_PUBLIC_API_URL ?? "https://polisdiff-ai.vercel.app/api").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, public code: string) { super(code); }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try { res = await fetch(`${API}/v1${path}`, init); } catch { throw new ApiError(0, "NETWORK"); }
  if (!res.ok) {
    let code = res.statusText;
    try { code = (await res.json()).detail ?? code; } catch { /* non-JSON error */ }
    throw new ApiError(res.status, String(code));
  }
  return res.json() as Promise<T>;
}
const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });

export const catalogue = () => call<Catalogue>("/catalogue");
export function check(file: File, language: Lang, applicableDate: string, mode = "hybrid",
                      browser?: { ranking: Record<string, string[]>; model: string }) {
  const form = new FormData();
  form.append("file", file); form.append("language", language); form.append("applicable_date", applicableDate); form.append("mode", mode);
  if (browser) { form.append("browser_ranking", JSON.stringify(browser.ranking)); form.append("browser_model", browser.model); }
  return call<CheckResponse>("/checks", { method: "POST", body: form });
}
export function passages(file: File) {
  const form = new FormData(); form.append("file", file);
  return call<{ sha256: string; passages: { id: string; text: string; section: string }[]; queries: Record<string, string[]> }>("/passages", { method: "POST", body: form });
}
export const advice = (report: unknown, language: Lang) => call<Plan>("/advice", json({ report, language }));
export const localize = (report: unknown, language: Lang) => call<View>("/localize", json({ report, language }));
export function page(file: File, number: number) {
  const form = new FormData(); form.append("file", file); form.append("number", String(number));
  return call<{ image: string }>("/pages", { method: "POST", body: form });
}
export const deadlines = (claim_date?: string, decision_date?: string) =>
  call<Clock>("/deadlines", json({ claim_date: claim_date || null, decision_date: decision_date || null }));
export const letter = (body: Record<string, unknown>) => call<Letter>("/letters", json(body));
export async function reportHtml(report: unknown, language: Lang): Promise<string> {
  const res = await fetch(`${API}/v1/report`, json({ report, language }));
  if (!res.ok) throw new ApiError(res.status, res.statusText);
  return res.text();
}
