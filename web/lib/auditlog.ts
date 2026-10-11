/* Hash-chained review log kept in this browser. Each entry commits to the previous one with SHA-256,
   so editing or deleting an earlier entry is detectable. It is not a shared or signed record. */
export interface LogEntry {
  index: number; at: string; document: string; documentSha256: string; ruleId: string;
  action: "confirm" | "dismiss" | "escalate"; reason: string; prev: string; hash: string;
}
const KEY = "polisdiff-review-log";
const GENESIS = "0".repeat(64);

async function sha256(text: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
const body = (e: Omit<LogEntry, "hash">) => JSON.stringify([e.index, e.at, e.document, e.documentSha256, e.ruleId, e.action, e.reason, e.prev]);

export function load(): LogEntry[] {
  try { return JSON.parse(localStorage.getItem(KEY) ?? "[]") as LogEntry[]; } catch { return []; }
}
function save(log: LogEntry[]) { try { localStorage.setItem(KEY, JSON.stringify(log)); } catch { /* storage may be blocked */ } }

export async function append(entry: Pick<LogEntry, "document" | "documentSha256" | "ruleId" | "action" | "reason">): Promise<LogEntry[]> {
  const log = load();
  const base = { ...entry, index: log.length, at: new Date().toISOString(), prev: log.at(-1)?.hash ?? GENESIS };
  const next = [...log, { ...base, hash: await sha256(body(base)) }];
  save(next);
  return next;
}

/** Returns the index of the first broken entry, or -1 if the chain is intact. */
export async function verify(log: LogEntry[] = load()): Promise<number> {
  let prev = GENESIS;
  for (const [i, e] of log.entries()) {
    const { hash, ...rest } = e;
    if (e.index !== i || e.prev !== prev || hash !== (await sha256(body(rest)))) return i;
    prev = hash;
  }
  return -1;
}
export function clear() { try { localStorage.removeItem(KEY); } catch { /* ignore */ } }

export function toCsv(log: LogEntry[]): string {
  const q = (v: string | number) => `"${String(v).replace(/"/g, '""')}"`;
  return ["index,at,document,document_sha256,rule,action,reason,hash", ...log.map((e) => [e.index, e.at, e.document, e.documentSha256, e.ruleId, e.action, e.reason, e.hash].map(q).join(","))].join("\n");
}
