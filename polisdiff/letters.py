"""Deterministic complaint/request letter drafts. No generated legal text.

A draft only restates what the document says (quote + page) and what the dated
provision says (quote + link), then asks the insurer to respond. Uzbek wording is an
unreviewed engineering draft; the user edits and sends it themselves.
"""
from .models import Finding, Report, Status
from .presentation import rule_name

UNREVIEWED = {"uz-Latn", "uz-Cyrl"}
T = {
    "ru": dict(
        to="Кому: {insurer}", sender="От: {name}", policy="Полис / договор №: {policy}",
        offer_conflict="Тема: несоответствие условия оферты ОСАГО нормативному акту",
        offer_body=("В документе «{doc}» (стр. {page}) указано: «{quote}».\n"
                    "Согласно {reference} (редакция {period}): «{law}».\n"
                    "Прошу привести условие в соответствие с нормой либо письменно пояснить, "
                    "почему оно применяется в таком виде."),
        late_decision=("Тема: нарушение срока уведомления о решении по заявлению о выплате",
                       "Я обратился(лась) с заявлением о страховой выплате {claim}. Срок уведомления о решении — не позднее {due} ({reference}: «{law}»). "
                       "Решение мне не сообщено. Прошу немедленно сообщить решение в письменной форме."),
        late_payment=("Тема: нарушение срока страховой выплаты",
                      "Решение о выплате принято {decision}. Срок выплаты — не позднее {due} ({reference}: «{law}»). "
                      "Выплата не произведена. Прошу произвести выплату и сообщить дату перечисления."),
        close="Ответ прошу направить в письменной форме. Дата: {today}.",
        note="Черновик, не юридическая консультация. Проверьте данные и отправьте самостоятельно."),
    "en": dict(
        to="To: {insurer}", sender="From: {name}", policy="Policy / contract no.: {policy}",
        offer_conflict="Subject: OSAGO offer term does not match the legal provision",
        offer_body=("The document \"{doc}\" (page {page}) states: \"{quote}\".\n"
                    "According to {reference} (version {period}): \"{law}\".\n"
                    "Please bring the term into line with the provision or explain in writing why it applies in this form."),
        late_decision=("Subject: missed deadline to notify the decision on my claim",
                       "I filed a claim for insurance compensation on {claim}. The decision had to be notified no later than {due} ({reference}: \"{law}\"). "
                       "I have not been told the decision. Please send the decision in writing without delay."),
        late_payment=("Subject: missed deadline for insurance payment",
                      "The decision to pay was taken on {decision}. Payment was due no later than {due} ({reference}: \"{law}\"). "
                      "No payment has been made. Please pay and confirm the transfer date."),
        close="Please reply in writing. Date: {today}.",
        note="Draft, not legal advice. Check the details and send it yourself."),
    "uz-Latn": dict(
        to="Kimga: {insurer}", sender="Kimdan: {name}", policy="Polis / shartnoma №: {policy}",
        offer_conflict="Mavzu: OSAGO taklifi sharti normativ hujjatga mos kelmaydi",
        offer_body=("«{doc}» hujjatida ({page}-bet) quyidagi ko‘rsatilgan: «{quote}».\n"
                    "{reference} ({period} tahriri) bo‘yicha: «{law}».\n"
                    "Shartni normaga moslashtirishingizni yoki nima uchun shunday qo‘llanilishini yozma tushuntirishingizni so‘rayman."),
        late_decision=("Mavzu: to‘lov to‘g‘risidagi qarorni xabar qilish muddati buzildi",
                       "Men {claim} sanasida sug‘urta tovoni uchun ariza berdim. Qaror {due} dan kechiktirmay xabar qilinishi kerak ({reference}: «{law}»). "
                       "Menga qaror xabar qilinmadi. Qarorni yozma ravishda zudlik bilan yuborishingizni so‘rayman."),
        late_payment=("Mavzu: sug‘urta to‘lovi muddati buzildi",
                      "To‘lov to‘g‘risidagi qaror {decision} sanasida qabul qilingan. To‘lov {due} dan kechiktirmay amalga oshirilishi kerak ({reference}: «{law}»). "
                      "To‘lov amalga oshirilmadi. To‘lovni amalga oshirib, o‘tkazma sanasini bildirishingizni so‘rayman."),
        close="Javobni yozma ravishda yuborishingizni so‘rayman. Sana: {today}.",
        note="Qoralama, yuridik maslahat emas. Ma’lumotlarni tekshirib, o‘zingiz yuboring."),
    "uz-Cyrl": dict(
        to="Кимга: {insurer}", sender="Кимдан: {name}", policy="Полис / шартнома №: {policy}",
        offer_conflict="Мавзу: ОСАГО таклифи шарти норматив ҳужжатга мос келмайди",
        offer_body=("«{doc}» ҳужжатида ({page}-бет) қуйидагича кўрсатилган: «{quote}».\n"
                    "{reference} ({period} таҳрири) бўйича: «{law}».\n"
                    "Шартни нормага мослаштиришингизни ёки нима учун шундай қўлланилишини ёзма тушунтиришингизни сўрайман."),
        late_decision=("Мавзу: тўлов тўғрисидаги қарорни хабар қилиш муддати бузилди",
                       "Мен {claim} санасида суғурта товони учун ариза бердим. Қарор {due} дан кечиктирмай хабар қилиниши керак ({reference}: «{law}»). "
                       "Менга қарор хабар қилинмади. Қарорни ёзма равишда зудлик билан юборишингизни сўрайман."),
        late_payment=("Мавзу: суғурта тўлови муддати бузилди",
                      "Тўлов тўғрисидаги қарор {decision} санасида қабул қилинган. Тўлов {due} дан кечиктирмай амалга оширилиши керак ({reference}: «{law}»). "
                      "Тўлов амалга оширилмади. Тўловни амалга ошириб, ўтказма санасини билдиришингизни сўрайман."),
        close="Жавобни ёзма равишда юборишингизни сўрайман. Сана: {today}.",
        note="Қоралама, юридик маслаҳат эмас. Маълумотларни текшириб, ўзингиз юборинг."),
}


def _header(t, insurer, name, policy):
    return [t["to"].format(insurer=insurer), t["sender"].format(name=name), t["policy"].format(policy=policy), ""]


def offer_conflict_letter(report: Report, finding: Finding, details: dict, language: str, document_name: str,
                          insurer="[insurer]", name="[your name]", policy="[number]", today="[date]") -> dict:
    """Only for a comparable potential conflict; refuses anything else."""
    if finding.status != Status.POTENTIAL_CONFLICT or not details.get("comparable") or not finding.evidence:
        raise ValueError("A complaint draft needs a comparable potential conflict")
    t, ev = T[language], finding.evidence[0]
    body = t["offer_body"].format(doc=document_name, page=ev.page, quote=ev.quote.strip(), reference=details["provision_reference"],
                                  period=details["period"], law=finding.source_quote)
    text = "\n".join(_header(t, insurer, name, policy) + [t["offer_conflict"], "", body, "", t["close"].format(today=today)])
    return {"kind": "offer_conflict", "text": text, "note": t["note"], "unreviewed": language in UNREVIEWED,
            "rule": rule_name(finding, language)}


def deadline_letter(kind: str, step: dict, language: str, claim="", decision="", insurer="[insurer]", name="[your name]",
                    policy="[number]", today="[date]") -> dict:
    if kind not in {"late_decision", "late_payment"}:
        raise ValueError("Unknown letter kind")
    t = T[language]
    subject, body = t[kind]
    text = "\n".join(_header(t, insurer, name, policy) + [subject, "",
                     body.format(claim=claim, decision=decision, due=step["due"], reference=step["reference"], law=step["source_quote"]),
                     "", t["close"].format(today=today)])
    return {"kind": kind, "text": text, "note": t["note"], "unreviewed": language in UNREVIEWED}
