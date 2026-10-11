"""Claim-clock calculator: the two OSAGO deadlines from the dated catalogue.

Decision notice: 15 days after a written/electronic claim (catalogue rule OSAGO_DECISION_NOTICE).
Payment: 5 working days after the insurer's decision to pay (rule OSAGO_PAYMENT).
Working days use the Mon-Fri week minus holidays in rules/holidays.json; unverified
periods are reported as caveats, never guessed.
"""
import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from .engine import load_catalogue

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def calendar():
    data = json.loads((ROOT / "rules" / "holidays.json").read_text(encoding="utf-8"))
    dated = {date.fromisoformat(d["date"]): d for d in data["dated_non_working_days"]}
    return data, dated


def holiday(day: date):
    data, dated = calendar()
    if day in dated:
        return dated[day]["name"]
    key = f"{day.month:02d}-{day.day:02d}"
    for month_day, name, _ in data["fixed_holidays"]:
        if month_day == key:
            return name
    return None


def is_working_day(day: date) -> bool:
    data, _ = calendar()
    return day.weekday() not in data["weekend_days"] and holiday(day) is None


def working_days_after(start: date, count: int) -> tuple[date, list[dict]]:
    """Last day of `count` working days counted from the day after `start`; also the skipped holidays."""
    day, counted, skipped = start, 0, []
    while counted < count:
        day += timedelta(days=1)
        if is_working_day(day):
            counted += 1
        elif (name := holiday(day)):
            skipped.append({"date": day.isoformat(), "name": name})
    return day, skipped


def caveats(start: date, end: date) -> list[str]:
    data, _ = calendar()
    return [p["text"] for p in data["unverified_periods"]
            if date.fromisoformat(p["from"]) <= end and start <= date.fromisoformat(p["to"])]


def _rule(rules, rule_id, on: date):
    rule = next(r for r in rules if r.id == rule_id)
    version = next((v for v in rule.versions if v.effective_from <= on and (v.effective_to is None or on <= v.effective_to)), None)
    return rule, version


def claim_clock(claim_date: date | None = None, decision_date: date | None = None) -> dict:
    catalogue, rules, _ = load_catalogue()
    first, last = (date.fromisoformat(d) for d in catalogue["supported_date_range"])
    out = {"catalogue_version": catalogue["catalogue_version"], "steps": [], "caveats": [],
           "week": "Mon-Fri; Saturday and Sunday are not working days"}
    if claim_date:
        rule, version = _rule(rules, "OSAGO_DECISION_NOTICE", claim_date)
        due = claim_date + timedelta(days=15)
        out["steps"].append({
            "key": "decision_notice", "label_from": claim_date.isoformat(), "due": due.isoformat(),
            "days": 15, "unit": "days", "rule_id": rule.id, "reference": rule.reference,
            "source_url": rule.official_source, "source_quote": version.source_quote if version else "",
            "in_supported_range": first <= claim_date <= last,
            "note": "The provision says fifteen days without the working-day modifier; calendar days are counted. Explicit working-day wording needs legal review."})
        out["caveats"] += caveats(claim_date, due)
    if decision_date:
        rule, version = _rule(rules, "OSAGO_PAYMENT", decision_date)
        due, skipped = working_days_after(decision_date, 5)
        out["steps"].append({
            "key": "payment", "label_from": decision_date.isoformat(), "due": due.isoformat(),
            "days": 5, "unit": "working_days", "rule_id": rule.id, "reference": rule.reference,
            "source_url": rule.official_source, "source_quote": version.source_quote if version else "",
            "in_supported_range": first <= decision_date <= last, "skipped_holidays": skipped, "note": ""})
        out["caveats"] += caveats(decision_date, due)
    out["caveats"] = list(dict.fromkeys(out["caveats"]))
    return out
