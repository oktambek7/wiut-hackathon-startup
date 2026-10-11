import type { ButtonHTMLAttributes, ReactNode } from "react";
import type { Level } from "@/lib/types";

export const LEVEL_STYLE: Record<Level | "info", string> = {
  ok: "bg-ok-bg text-ok", attention: "bg-attn-bg text-attn", missing: "bg-miss-bg text-miss", unknown: "bg-unk-bg text-unk", info: "bg-brand-soft text-brand",
};
export const LEVEL_BORDER: Record<Level, string> = { ok: "border-l-ok", attention: "border-l-attn", missing: "border-l-miss", unknown: "border-l-unk" };

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-2xl border border-line bg-surface p-5 shadow-sm ${className}`}>{children}</section>;
}

export function Badge({ level, children }: { level: Level | "info"; children: ReactNode }) {
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold ${LEVEL_STYLE[level]}`}>{children}</span>;
}

export function Button({ variant = "secondary", className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" }) {
  const base = "inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50";
  const styles = {
    primary: "bg-brand text-brand-ink hover:opacity-90",
    secondary: "border border-line bg-surface hover:bg-surface-2",
    ghost: "text-brand hover:bg-brand-soft",
  };
  return <button type="button" className={`${base} ${styles[variant]} ${className}`} {...props} />;
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-semibold">{label}</span>
      {children}
      {hint && <span className="block text-sm text-muted">{hint}</span>}
    </label>
  );
}
export const inputClass = "min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-base";

export function ErrorNote({ children }: { children: ReactNode }) {
  return <p role="alert" className="rounded-xl bg-attn-bg px-4 py-3 text-attn">{children}</p>;
}
