"""Deterministic extraction and conservative, date-aware evidence screening."""
from datetime import date
from pathlib import Path
import hashlib
import json
import re
from .models import Rule, Finding, Evidence, Status, Document, Passage
from .text import parse_number

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "rules" / "catalogue.v1.json"


def load_catalogue():
    raw = CATALOGUE.read_bytes()
    data = json.loads(raw)
    return data, [Rule.model_validate(r) for r in data["rules"]], hashlib.sha256(raw).hexdigest()


def evidence(p: Passage, value=None, unit=None) -> Evidence:
    return Evidence(passage_id=p.id, page=p.page, quote=p.text, start=p.start,
        end=p.end, bbox=p.bbox, section=p.section, extracted_value=value, unit=unit)


SUM = (r"(?:страхов\w*\s+сумм\w*|sug'urta\s+(?:summasi|puli)\b|суғурта\s+(?:суммаси|пули)\b|"
       r"(?:insurance\s+sum|sum\s+insured|insured\s+sum)\b)")
NUMBER = r"\d+(?:[ \u00a0\u202f.,'’]\d+)*"
MONEY = re.compile(r"(" + NUMBER + r")\s*(млн\.?|миллион\w*|million\w*)?\s*(?:\([^)]{1,65}\)\s*)?(сум\b|сўм(?:ни)?\b|so'm(?:ni)?\b|uzs\b|soums?\b|sums?\b)")
DAYS = re.compile(r"(?P<n>\d+|пятнадцат\w*|пят[ьи]|o'n besh|ўн беш|besh|беш|десять|o'n|ўн|yetti|етти|семь|fifteen|five|seven|ten)\s*"
                  r"(?P<u>рабоч\w*\s+|календарн\w*\s+|ish\s+|иш\s+|kalendar\s+|календар\s+|working\s+|business\s+|calendar\s+)?"
                  r"(?:дней|дня|день|kun\w*|кун\w*|days?\b)")
# The event that starts each deadline. Shared by extraction and highlighting so both use the same words.
PAYMENT_TRIGGER = re.compile(
    r"(?:со дня|с момента|после) принятия решения страховщик\w*|"
    r"(?:qaror\w* qabul qilingan|қарор\w* қабул қилинган)|"
    r"(?:from|after|following)\s+(?:the\s+)?(?:(?:date|day|moment)\s+)?(?:of\s+)?(?:the\s+)?"
    r"(?:(?:adoption|taking|making)\s+of\s+)?(?:the\s+)?(?:insurer|insurance company)(?:'s?)?\s+(?:payment\s+)?decision")
NOTICE_REQUEST = re.compile(
    r"(?:после|со дня|с момента) (?:получения |поступления )?(?:его |ее |её )?"
    r"(?:письмен\w*|электрон\w*)(?: или (?:письмен\w*|электрон\w*))? (?:обращени\w*|заявлен\w*)|"
    r"(?:yozma|elektron) (?:ariza\w*|murojaat\w*)\s*(?:so'ng|keyin)|"
    r"(?:ёзма|электрон) (?:ариза\w*|мурожаат\w*)\s*(?:сўнг|кейин)|"
    r"(?:after|from|following)\s+(?:the\s+)?(?:(?:date\s+of\s+)?(?:receipt|receiving)\s+of\s+(?:the\s+|a\s+|his\s+|her\s+)?)?"
    r"(?:written|electronic)(?:\s+or\s+(?:written|electronic))?\s+(?:claim|application|request|notification)")


def context_pattern(rule: Rule):
    """Words that define what a value means (subject or trigger event); highlighted next to the value."""
    return {"sum": re.compile(SUM), "payment_days": PAYMENT_TRIGGER, "decision_days": NOTICE_REQUEST}[rule.logic]


def topic(rule: Rule, text: str) -> bool:
    if rule.logic == "sum":
        return bool(re.search(SUM, text))
    compensation = bool(re.search(r"возмещ|tovon|товон|compensat|indemn", text))
    decision = bool(re.search(r"решени|qaror|қарор|\bdecision", text))
    if rule.logic == "payment_days":
        # Finite transfer verbs only; a notice 'о перечислении' is not payment.
        transfer = r"перечисляется|перечисляются|перечислит|перечислят|\bis paid\b|\bare paid\b|\btransferred\b"
        payment = bool(re.search(r"выпла[тч]|осуществ|to'la|тўла|amalga|амалга|\bpaid\b|\bpayable\b|\bpayment\b|" + transfer, text))
        # Notification clauses also mention payment decisions; preserve event distinction.
        notice_only = (bool(re.search(r"сообщ|уведом|xabar|хабар|notif|\binform", text))
                       and not bool(re.search(r"осуществ|производ|amalga|амалга|выплачивается|payment (?:is|shall be) made|" + transfer, text)))
        return compensation and decision and payment and not notice_only
    return compensation and decision and bool(re.search(r"сообщ|уведом|xabar|хабар|bildir|билдир|notif|\binform", text))


def extract_value(rule: Rule, text: str):
    """Return value, unit, abstention reason. Never substitute expected values."""
    # Conditional, illustrative or negated terms need an expert to scope the rule.
    if re.search(r"\b(?:если|agar|агар|например|masalan|масалан)\b|не обязан|не выплач|не перечисл|to'lanmay|тўланмай|emas\b|эмас\b|не ранее|kamida|камида|"
                 r"\b(?:if|unless|for example|for instance)\b|e\.g\.|\bnot (?:obliged|required|liable) to\b|\bshall not\b|not earlier than|\bat least\b", text):
        return None, None, "Условие, пример или отрицание требуют ручного толкования."
    if rule.logic == "sum":
        concept = re.search(SUM, text)
        if not concept:
            return None, None, "Не установлен контекст общей страховой суммы."
        window = text[concept.end():concept.end()+160]
        if re.search(r"преми|мукофот|mukofot|mol-mulk|мол-мулк|имуществ|hayot|ҳаёт|premium|property|\blife\b|health|sub-?limit", window[:60]):
            return None, None, "Возможна премия или частичный лимит вместо общей суммы."
        matches = list(MONEY.finditer(window))
        if len(matches) != 1:
            return None, None, "Сумма/валюта отсутствует либо содержит несколько значений."
        m = matches[0]
        try:
            value = parse_number(m[1]) * (1_000_000 if m[2] else 1)
        except ValueError:
            return None, None, "Неоднозначный формат числа."
        if re.search(r"до\s*$|не более\s*$|gacha|гача|kam|кам|ortiq|ортиқ|более|свыше|от\s+\d|up to|not more than|no more than|at most|more than|exceed|less than|maximum|minimum", window[:m.start()] + window[m.end():]):
            return None, None, "Диапазон или неравенство суммы требует ручного толкования."
        return value, "UZS", None
    matches = list(DAYS.finditer(text))
    if len(matches) != 1:
        return None, None, "Не найден единственный поддерживаемый срок в днях."
    m = matches[0]
    n = m["n"]
    value = float(n) if n.isdigit() else (15 if n.startswith("пятнадцат") or n in {"o'n besh", "ўн беш", "fifteen"} else
        5 if n in {"пять", "пяти", "besh", "беш", "five"} else 7 if n in {"yetti", "етти", "семь", "seven"} else 10)
    unit = "working_days" if m["u"] and re.search(r"рабоч|ish|иш|working|business", m["u"]) else "days"
    if rule.logic == "payment_days":
        # Adoption must belong to the insurer's decision, not an application or court.
        trigger = bool(PAYMENT_TRIGGER.search(text))
        if not trigger:
            return value, unit, "Не подтвержден отсчет от принятия решения страховщиком."
        if unit != "working_days":
            return value, unit, "Не подтверждены рабочие дни; календарные дни нельзя сравнить автоматически."
    else:
        request = bool(NOTICE_REQUEST.search(text))
        recipient = bool(re.search(r"страховател|sug'urta qildiruvchi|суғурта қилдирувчи|policyholder|insured person", text))
        if not (request and recipient):
            return value, unit, "Не подтверждены обращение и адресат уведомления."
        if unit == "working_days":
            return value, unit, "В норме не указаны рабочие дни; требуется правовое толкование."
    return value, unit, None


def evaluate(rule: Rule, doc: Document, candidates: list[Passage], applicable_date: date | None, audit_date: date) -> Finding:
    catalogue, _, _ = load_catalogue()
    verified_until = date.fromisoformat(catalogue["verified_access_date"])
    supported_from = date.fromisoformat(catalogue["supported_date_range"][0])
    version = next((v for v in rule.versions if applicable_date and v.effective_from <= applicable_date and
                    (v.effective_to is None or applicable_date <= v.effective_to)), None)
    base = dict(rule_id=rule.id, rule_name=rule.name, source_url=version.source_url if version else rule.official_source,
        provision_reference=rule.reference, source_quote=version.source_quote if version else "",
        effective_from=version.effective_from if version else None, effective_to=version.effective_to if version else None,
        expected_value=version.expected if version else None,
        check_scope=rule.applicability, source_version_note=version.version_note if version else "")
    relevant = [p for p in candidates if topic(rule, p.normalized)]
    def result(status, reason, ev=None, uncertainty=None):
        return Finding(**base, status=status, reason=reason, evidence=ev or [], uncertainty=uncertainty or [])
    if applicable_date is None:
        return result(Status.UNVERIFIABLE, "Дата применимости договора не подтверждена. Дата аудита не заменяет дату договора.",
                      [evidence(p) for p in relevant[:3]], ["applicable_date_unknown"])
    if applicable_date > audit_date or applicable_date > verified_until or applicable_date < supported_from or version is None:
        base.update(expected_value=None, effective_from=None, effective_to=None,
                    source_quote="", source_version_note="", source_url=rule.official_source)
        return result(Status.UNVERIFIABLE, "Дата вне подтвержденного диапазона версий либо позже даты аудита.",
                      [evidence(p) for p in relevant[:3]], ["unsupported_applicability_date"])
    offer = [p for p in relevant if p.section == "offer"]
    appendix = [p for p in relevant if p.section != "offer"]
    if not offer:
        if appendix:
            return result(Status.UNVERIFIABLE, "Текст найден только в предполагаемом нормативном приложении; условие автора оферты не подтверждено.",
                          [evidence(p) for p in appendix[:3]], ["appendix_only"])
        if doc.governing_reference:
            return result(Status.UNVERIFIABLE, "Есть ссылка на правила №141; включение условий по ссылке требует правовой проверки.",
                          [evidence(p) for p in doc.governing_reference[:2]], ["incorporation_by_reference"])
        if any(not page.readable for page in doc.pages):
            return result(Status.UNVERIFIABLE, "Часть документа не читается. Отсутствие условия не установлено.", uncertainty=["unreadable_pages"])
        return result(Status.NOT_FOUND, "В извлеченном тексте и выбранных поиском фрагментах условие не найдено. Это не доказательство нарушения.", uncertainty=["retrieval_may_miss_evidence"])
    extracted, uncertain = [], []
    for p in offer:
        value, unit, problem = extract_value(rule, p.normalized)
        if problem:
            uncertain.append((evidence(p, value, unit), problem))
        else:
            extracted.append(evidence(p, value, unit))
    if extracted:
        # General definitions/headings without numeric constraints do not compete
        # with a complete numeric contractual term. Keep negations and conditions.
        uncertain = [(ev, reason) for ev, reason in uncertain if
            re.search(r"\d|беш|besh|пят|ўн|o'n|не обязан|to'lanmay|тўланмай|не выплач|emas\b|эмас\b|five|fifteen|seven|\bten\b|\bnot (?:obliged|required)", ev.quote.casefold())
            or reason == "Условие, пример или отрицание требуют ручного толкования."]
    if not extracted:
        return result(Status.UNVERIFIABLE, uncertain[0][1], [e for e, _ in uncertain[:3]], [reason for _, reason in uncertain])
    values = {e.extracted_value for e in extracted}
    if len(values) > 1 or uncertain:
        return result(Status.UNVERIFIABLE, "Найдены конкурирующие значения или неоднозначные условия; требуется проверка контекста.",
                      extracted[:3] + [e for e, _ in uncertain[:2]], ["competing_or_ambiguous_terms"])
    actual = extracted[0].extracted_value
    conflict = actual != version.expected if rule.logic == "sum" else actual > version.expected
    if conflict:
        return result(Status.POTENTIAL_CONFLICT, f"Явное значение {actual:g} {extracted[0].unit} потенциально противоречит ориентиру {version.expected:g} для выбранной даты. Требуется правовая проверка.", extracted[:3])
    return result(Status.MATCH_FOUND, "Найдено явное условие, согласующееся с числовым ориентиром и проверяемым событием. Вывод касается только этого условия.", extracted[:3])
