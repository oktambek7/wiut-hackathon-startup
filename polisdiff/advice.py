"""Action plan shown at the end of a check: what the person can do next.

Built from the engine's verified findings only. Each action names the rule it comes from.
If an AI writing model is reachable (Vercel AI Gateway), it may rephrase the plan, but its
output is accepted only when every number it mentions already appears in the findings;
otherwise the deterministic plan is returned. The plan is never legal advice.
"""
import json
import os
import re
import time

from .models import Report, Status
from .presentation import finding_details, next_step, rule_name

T = {
    "en": dict(
        conflict_title="Ask the insurer to correct: {rule}",
        conflict_detail="{cmp} The clause is on page {page}. Before you sign or pay, ask for a written correction or explanation; the letter draft does this for you.",
        missing_title="Ask where this term is: {rule}",
        missing_detail="We did not find this term in the text we read. Ask the insurer to point to the clause or confirm it in writing. A missing clause is not proof of a violation.",
        date_title="Confirm the contract date",
        date_detail="Without the date the policy applies from, the terms cannot be compared with the law version in force. Enter it and run the check again.",
        manual_title="Check by hand: {rule}",
        manual_detail="We could not compare this term automatically: {why}",
        ok_title="Keep for your records: {rule}",
        ok_detail="This term matches the law version for your date. The check covers only this term, not the whole contract.",
        clock_title="Note your claim deadlines",
        clock_detail="If you claim, the insurer must tell you its decision within 15 days of your written claim and pay within 5 working days of deciding to pay. Use Claim deadlines to get exact dates.",
        keep_title="Save the report",
        keep_detail="Download the report with the quotes and page numbers. It helps if you need to complain later.",
        summary_conflict="{n} term(s) in this offer differ from the law. Start with the high-priority steps.",
        summary_date="Confirm the contract date first; nothing was compared with the law yet.",
        summary_ok="No differences were found in the checked terms. Keep the report and note the claim deadlines.",
        summary_partial="Some terms could not be checked automatically. Follow the steps below.",
        cmp_deadline="The offer gives the insurer {offer} {unit}; the law allows {law}.",
        cmp_amount="The offer states a total insurance sum of {offer}; the law sets {law}.",
        units={"working_days": "working days", "days": "days", "UZS": "UZS"}),
    "ru": dict(
        conflict_title="Попросите страховщика исправить: {rule}",
        conflict_detail="{cmp} Условие — на странице {page}. До подписания или оплаты попросите письменное исправление или объяснение; черновик письма поможет.",
        missing_title="Уточните, где указано условие: {rule}",
        missing_detail="Мы не нашли это условие в прочитанном тексте. Попросите страховщика указать пункт или подтвердить письменно. Отсутствие пункта не доказывает нарушение.",
        date_title="Подтвердите дату договора",
        date_detail="Без даты, с которой действует полис, условия нельзя сравнить с действующей редакцией закона. Укажите её и повторите проверку.",
        manual_title="Проверьте вручную: {rule}",
        manual_detail="Автоматически сравнить не удалось: {why}",
        ok_title="Сохраните для себя: {rule}",
        ok_detail="Условие совпадает с редакцией закона на вашу дату. Проверка касается только этого условия, а не всего договора.",
        clock_title="Запомните сроки по заявлению",
        clock_detail="При заявлении страховщик должен сообщить решение в течение 15 дней после письменного обращения и выплатить в течение 5 рабочих дней после решения о выплате. Точные даты — в разделе «Сроки по заявлению».",
        keep_title="Сохраните отчёт",
        keep_detail="Скачайте отчёт с цитатами и номерами страниц. Он пригодится, если понадобится жалоба.",
        summary_conflict="Условий, отличающихся от закона: {n}. Начните с шагов высокого приоритета.",
        summary_date="Сначала подтвердите дату договора: сравнение с законом ещё не выполнено.",
        summary_ok="В проверенных условиях расхождений не найдено. Сохраните отчёт и запомните сроки по заявлению.",
        summary_partial="Часть условий не удалось проверить автоматически. Выполните шаги ниже.",
        cmp_deadline="Оферта даёт страховщику {offer} {unit}; закон допускает {law}.",
        cmp_amount="В оферте общая страховая сумма {offer}; закон устанавливает {law}.",
        units={"working_days": "рабочих дней", "days": "дней", "UZS": "сум"}),
    "uz-Latn": dict(
        conflict_title="Sug‘urtachidan tuzatishni so‘rang: {rule}",
        conflict_detail="{cmp} Band {page}-betda. Imzolash yoki to‘lashdan oldin yozma tuzatish yoki tushuntirish so‘rang; xat qoralamasi yordam beradi.",
        missing_title="Bu shart qayerda ekanini so‘rang: {rule}",
        missing_detail="Biz o‘qigan matnda bu shart topilmadi. Sug‘urtachidan bandni ko‘rsatishni yoki yozma tasdiqlashni so‘rang. Band yo‘qligi buzilish isboti emas.",
        date_title="Shartnoma sanasini tasdiqlang",
        date_detail="Polis amal qila boshlagan sanasiz shartlarni amaldagi qonun tahriri bilan solishtirib bo‘lmaydi. Sanani kiriting va tekshiruvni takrorlang.",
        manual_title="Qo‘lda tekshiring: {rule}",
        manual_detail="Avtomatik solishtirib bo‘lmadi: {why}",
        ok_title="O‘zingiz uchun saqlang: {rule}",
        ok_detail="Shart sizning sanangiz uchun qonun tahririga mos. Tekshiruv faqat shu shartga tegishli, butun shartnomaga emas.",
        clock_title="Ariza muddatlarini yodda tuting",
        clock_detail="Ariza berilganda sug‘urtachi yozma murojaatdan keyin 15 kun ichida qarorni xabar qilishi va to‘lov qaroridan keyin 5 ish kuni ichida to‘lashi shart. Aniq sanalar — «Ariza muddatlari» bo‘limida.",
        keep_title="Hisobotni saqlang",
        keep_detail="Iqtiboslar va sahifa raqamlari bilan hisobotni yuklab oling. Keyin shikoyat kerak bo‘lsa, foydali bo‘ladi.",
        summary_conflict="Qonundan farq qiladigan shartlar: {n}. Yuqori ustuvorlikdagi qadamlardan boshlang.",
        summary_date="Avval shartnoma sanasini tasdiqlang: qonun bilan solishtirish hali bajarilmagan.",
        summary_ok="Tekshirilgan shartlarda farq topilmadi. Hisobotni saqlang va ariza muddatlarini yodda tuting.",
        summary_partial="Ayrim shartlarni avtomatik tekshirib bo‘lmadi. Quyidagi qadamlarni bajaring.",
        cmp_deadline="Taklif sug‘urtachiga {offer} {unit} beradi; qonun {law} ruxsat beradi.",
        cmp_amount="Taklifdagi umumiy sug‘urta summasi {offer}; qonun {law} belgilaydi.",
        units={"working_days": "ish kuni", "days": "kun", "UZS": "so‘m"}),
    "uz-Cyrl": dict(
        conflict_title="Суғурталовчидан тузатишни сўранг: {rule}",
        conflict_detail="{cmp} Банд {page}-бетда. Имзолаш ёки тўлашдан олдин ёзма тузатиш ёки тушунтириш сўранг; хат қораламаси ёрдам беради.",
        missing_title="Бу шарт қаерда эканини сўранг: {rule}",
        missing_detail="Биз ўқиган матнда бу шарт топилмади. Суғурталовчидан бандни кўрсатишни ёки ёзма тасдиқлашни сўранг. Банд йўқлиги бузилиш исботи эмас.",
        date_title="Шартнома санасини тасдиқланг",
        date_detail="Полис амал қила бошлаган санасиз шартларни амалдаги қонун таҳрири билан солиштириб бўлмайди. Санани киритинг ва текширувни такрорланг.",
        manual_title="Қўлда текширинг: {rule}",
        manual_detail="Автоматик солиштириб бўлмади: {why}",
        ok_title="Ўзингиз учун сақланг: {rule}",
        ok_detail="Шарт сизнинг санангиз учун қонун таҳририга мос. Текширув фақат шу шартга тегишли, бутун шартномага эмас.",
        clock_title="Ариза муддатларини ёдда тутинг",
        clock_detail="Ариза берилганда суғурталовчи ёзма мурожаатдан кейин 15 кун ичида қарорни хабар қилиши ва тўлов қароридан кейин 5 иш куни ичида тўлаши шарт. Аниқ саналар — «Ариза муддатлари» бўлимида.",
        keep_title="Ҳисоботни сақланг",
        keep_detail="Иқтибослар ва саҳифа рақамлари билан ҳисоботни юклаб олинг. Кейин шикоят керак бўлса, фойдали бўлади.",
        summary_conflict="Қонундан фарқ қиладиган шартлар: {n}. Юқори устуворликдаги қадамлардан бошланг.",
        summary_date="Аввал шартнома санасини тасдиқланг: қонун билан солиштириш ҳали бажарилмаган.",
        summary_ok="Текширилган шартларда фарқ топилмади. Ҳисоботни сақланг ва ариза муддатларини ёдда тутинг.",
        summary_partial="Айрим шартларни автоматик текшириб бўлмади. Қуйидаги қадамларни бажаринг.",
        cmp_deadline="Таклиф суғурталовчига {offer} {unit} беради; қонун {law} рухсат беради.",
        cmp_amount="Таклифдаги умумий суғурта суммаси {offer}; қонун {law} белгилайди.",
        units={"working_days": "иш куни", "days": "кун", "UZS": "сўм"}),
}
PRIORITY = {"high": 0, "medium": 1, "low": 2}
_blocked_until = 0.0


def _num(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def rules_plan(report: Report, language: str) -> dict:
    t = T[language]
    actions = []
    pending = report.applicable_date is None
    conflicts = 0
    for f in report.findings:
        d = finding_details(report, f, language)
        name = rule_name(f, language)
        if pending:
            continue
        if f.status == Status.POTENTIAL_CONFLICT and d["comparable"]:
            conflicts += 1
            ev = f.evidence[0]
            unit = t["units"].get(ev.unit or "", "")
            cmp = (t["cmp_amount"].format(offer=f"{_num(ev.extracted_value)} {unit}", law=f"{_num(f.expected_value)} {unit}")
                   if f.rule_id == "OSAGO_SUM" else
                   t["cmp_deadline"].format(offer=_num(ev.extracted_value), unit=unit, law=f"{_num(f.expected_value)} {unit}"))
            actions.append({"priority": "high", "kind": "letter", "rule_id": f.rule_id,
                            "title": t["conflict_title"].format(rule=name), "detail": t["conflict_detail"].format(cmp=cmp, page=ev.page)})
        elif f.status == Status.NOT_FOUND:
            actions.append({"priority": "medium", "kind": "ask", "rule_id": f.rule_id,
                            "title": t["missing_title"].format(rule=name), "detail": t["missing_detail"]})
        elif f.status == Status.UNVERIFIABLE:
            why = "; ".join(d["blockers"]) or next_step(f, language)
            actions.append({"priority": "medium", "kind": "review", "rule_id": f.rule_id,
                            "title": t["manual_title"].format(rule=name), "detail": t["manual_detail"].format(why=why)})
        else:
            actions.append({"priority": "low", "kind": "keep", "rule_id": f.rule_id,
                            "title": t["ok_title"].format(rule=name), "detail": t["ok_detail"]})
    if pending:
        actions.append({"priority": "high", "kind": "date", "rule_id": None, "title": t["date_title"], "detail": t["date_detail"]})
    actions.append({"priority": "medium", "kind": "deadlines", "rule_id": None, "title": t["clock_title"], "detail": t["clock_detail"]})
    actions.append({"priority": "low", "kind": "report", "rule_id": None, "title": t["keep_title"], "detail": t["keep_detail"]})
    actions.sort(key=lambda a: PRIORITY[a["priority"]])
    if pending:
        summary = t["summary_date"]
    elif conflicts:
        summary = t["summary_conflict"].format(n=conflicts)
    elif any(a["kind"] in {"review", "ask"} for a in actions):
        summary = t["summary_partial"]
    else:
        summary = t["summary_ok"]
    return {"source": "rules", "model": None, "summary": summary, "actions": actions}


def _numbers(text: str) -> set[str]:
    return {re.sub(r"[\s,. ]", "", n) for n in re.findall(r"\d[\d\s,. ]*", text)}


def grounded(candidate: dict, plan: dict, report: Report) -> bool:
    """Accept AI wording only if it adds no number, rule or action that the verified plan lacks."""
    facts = json.dumps(plan, ensure_ascii=False) + report.model_dump_json()
    allowed = _numbers(facts)
    texts = [candidate.get("summary", "")] + [a.get("title", "") + " " + a.get("detail", "") for a in candidate.get("actions", [])]
    rule_ids = {f.rule_id for f in report.findings} | {None}
    if len(candidate.get("actions", [])) != len(plan["actions"]):
        return False
    if any(a.get("rule_id") not in rule_ids or a.get("kind") != b["kind"] for a, b in zip(candidate["actions"], plan["actions"])):
        return False
    return all(_numbers(text) <= allowed for text in texts)


def ai_plan(report: Report, language: str, plan: dict) -> dict | None:
    """Optional rewording through Vercel AI Gateway; None when unavailable or not grounded."""
    global _blocked_until
    token = os.getenv("AI_GATEWAY_API_KEY") or os.getenv("VERCEL_OIDC_TOKEN")
    # Opt-in: sending findings to an external model must be a deliberate operator choice.
    if not token or os.getenv("POLISDIFF_AI_WRITER", "0") != "1" or time.monotonic() < _blocked_until:
        return None
    import requests
    model = os.getenv("POLISDIFF_AI_WRITER_MODEL", "anthropic/claude-haiku-5.5")
    system = ("You rewrite an insurance buyer's action plan in plain, friendly language. Keep the same number of actions, in the same "
              "order, with the same 'kind', 'priority' and 'rule_id'. Use only facts from the input. Do not add numbers, laws, "
              "phone numbers, organisations or promises. A missing clause is not a violation. Reply with JSON only: "
              '{"summary": str, "actions": [{"priority","kind","rule_id","title","detail"}]}. Language: ' + language)
    started = time.perf_counter()
    try:
        reply = requests.post("https://ai-gateway.vercel.sh/v1/chat/completions", timeout=20,
                              headers={"Authorization": f"Bearer {token}"},
                              json={"model": model, "max_tokens": 1500, "temperature": 0,
                                    "messages": [{"role": "system", "content": system},
                                                 {"role": "user", "content": json.dumps(plan, ensure_ascii=False)}]})
        if not reply.ok:
            if reply.status_code in {401, 402, 403}:
                _blocked_until = time.monotonic() + 600  # account not enabled; do not retry on every check
            return None
        text = reply.json()["choices"][0]["message"]["content"]
        candidate = json.loads(text[text.find("{"): text.rfind("}") + 1])
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        return None
    if not isinstance(candidate, dict) or not grounded(candidate, plan, report):
        return None
    return {"source": "ai", "model": model, "summary": candidate["summary"], "actions": [
        {**b, "title": a["title"], "detail": a["detail"]} for a, b in zip(candidate["actions"], plan["actions"])],
        "seconds": round(time.perf_counter() - started, 2)}


def action_plan(report: Report, language: str) -> dict:
    plan = rules_plan(report, language)
    return ai_plan(report, language, plan) or plan
