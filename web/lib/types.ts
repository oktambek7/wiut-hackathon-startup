export type Lang = "ru" | "uz-Latn" | "uz-Cyrl" | "en";
export type Level = "ok" | "attention" | "missing" | "unknown";

export interface Evidence { passage_id: string; page: number; section: string; section_label: string; quote: string; quote_html: string }
export interface Check {
  rule_id: string; name: string; status: string; level: Level; status_label: string; icon: string; pending_date: boolean;
  offer_says: string; law_says: string; meaning: string; next_step: string; verification: string[]; remediation: string;
  can_complain: boolean; evidence: Evidence[]; blockers: string[];
  comparison: { kind: "amount" | "deadline"; offer: number; law: number; unit: string; difference: number; direction: "worse" | "better" | "same" } | null;
  law: { reference: string; provision: string; period: string; source_url: string; source_quote: string; date_note: string };
}
export interface View { language: Lang; level: "ok" | "attention" | "unknown"; headline: string; counts: Record<string, number>; checks: Check[]; warnings: string[] }
export interface Doc { name: string; pages: number; languages: string[]; unreadable_pages: number[]; detected_dates: string[]; page_sections: Record<string, string> }
export interface CheckResponse {
  view: View; report: Record<string, unknown>; doc: Doc; images: Record<string, string>; suggested_dates: string[];
  focus?: Record<string, string>; highlight?: Record<string, string>;
  engine: { retrieval_used: string; ai_fallback: boolean; analysis_seconds: number; render_seconds: number; total_seconds: number };
}
export interface Step {
  key: "decision_notice" | "payment"; label_from: string; due: string; days: number; unit: string; rule_id: string; reference: string;
  source_url: string; source_quote: string; in_supported_range: boolean; note: string; skipped_holidays?: { date: string; name: string }[];
}
export interface Clock { catalogue_version: string; steps: Step[]; caveats: string[]; week: string }
export interface Letter { kind: string; text: string; note: string; unreviewed: boolean }
export interface Catalogue { version: string; sha256: string; supported_date_range: [string, string]; max_upload_bytes: number; rules: { id: string; reference: string; source_url: string }[] }
export interface Sample { id: string; file: string; case: string; language: string; applicable_date: string }
