"""Search transforms are separate from original documentary evidence."""
import re
import unicodedata

APOSTROPHES = "‘’ʻʼ`´ʹ＇"


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text.replace("№", " № ")).casefold()
    text = text.translate(str.maketrans({c: "'" for c in APOSTROPHES}))
    text = text.replace("\u00ad", "").replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()


def detect_languages(text: str) -> list[str]:
    """Passage-level script + conservative vocabulary cues; not a full classifier."""
    s = normalize(text)
    labels = []
    has_lat = bool(re.search(r"[a-z]", s))
    has_cyr = bool(re.search(r"[а-яёўқғҳ]", s))
    uz_lat = bool(re.search(r"sug'ur|sugur|to'lov|tovon|shartnoma|qaror|kun|summa|so'm|majburiy", s))
    uz_cyr = bool(re.search(r"[ўқғҳ]|суғур|товон|кун|шартнома|қарор", s))
    ru = bool(re.search(r"страх|возмещ|решени|рабоч|уведом|дней|дня|руб|сум", s))
    en = bool(re.search(r"\b(?:the|insurance|insurer|policyholder|compensation|payment|days|decision)\b", s))
    if has_lat:
        if uz_lat:
            labels.append("uz-Latn")
        if en:
            labels.append("en")
        if not (uz_lat or en):
            labels.append("Latin-undetermined")
    if has_cyr:
        if uz_cyr:
            labels.append("uz-Cyrl")
        if ru:
            labels.append("ru-Cyrl")
        if not (uz_cyr or ru):
            labels.append("Cyrillic-undetermined")
    return labels or ["undetermined"]


def parse_number(value: str) -> float:
    s = re.sub(r"[\s\u00a0\u202f'’]", "", value)
    if "," in s and "." in s:
        decimal = "," if s.rfind(",") > s.rfind(".") else "."
        s = s.replace("." if decimal == "," else ",", "").replace(decimal, ".")
    elif re.fullmatch(r"\d{1,3}([.,]\d{3})+", s):
        s = s.replace(",", "").replace(".", "")
    else:
        s = s.replace(",", ".")
    return float(s)


def extract_dates(text: str):
    from datetime import date
    dates = set()
    for day, month, year in re.findall(r"\b(\d{2})[./-](\d{2})[./-](20\d{2})\b", text):
        try:
            dates.add(date(int(year), int(month), int(day)))
        except ValueError:
            pass
    for year, month, day in re.findall(r"\b(20\d{2})-(\d{2})-(\d{2})\b", text):
        try:
            dates.add(date(int(year), int(month), int(day)))
        except ValueError:
            pass
    return sorted(dates)
