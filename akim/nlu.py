import re

MEASURE_WORDS = {
    "M1": r"brt|автобусн\w*\s+полос|выделенн\w*\s+полос", "M2": r"светофор", "M3": r"лрт|lrt|скоростн\w*\s+трамва",
    "M4": r"парк|сквер", "M5": r"топлив|частн\w*\s+сектор|газифик", "M6": r"озеленени\w*\s+и\s+ветро|ветрозащит",
    "M7": r"школ|детсад|детск\w*\s+сад", "M8": r"поликлиник|центр\w*\s+семейн", "M9": r"спорт",
    "M10": r"камер|освещени|safe\s*city", "M11": r"переход|школьн\w*\s+зон", "M12": r"платформ\w*\s+обращ|обращени",
    "M13": r"теплосет|водосет|тепло-?\s*и\s*водо|модернизац\w*\s+сет", "M14": r"аварийн\w*\s+бригад|бригад|оповещени",
}
INDICATOR_WORDS = {
    "T1": r"пробк|разгрузк\w*\s+дорог|загруженност", "T2": r"общественн\w*\s+транспорт|остановк",
    "E1": r"озеленени|зелен", "E2": r"воздух|смог", "S1": r"школ|детсад", "S2": r"поликлиник|медицин|медпом",
    "B1": r"безопасност\w*\s+улиц|освещени|камер", "B2": r"дтп|безопасност\w*\s+(дорожн|движени)",
    "C1": r"жкх|теплосет|отоплени|водоснаб", "C2": r"обращени",
}
DISTRICT_STEMS = {"Есиль": r"есил", "Алматы": r"алмат", "Сарыарка": r"сарыарк", "Байконур": r"байконур",
                  "Нура": r"\bнур"}

_KEEP = r"(сохрани|оставь|оставить|не\s+трогай|не\s+убирай|закрепи)"
_EXCLUDE = r"(без|исключи|убери|не\s+(надо|нужн\w*|бери|используй))"
_PROTECT = r"(не\s+(ухудш|снижа|опуска|трога)|не\s+хуже|чтобы\s+не\s+(упал|стал\w*\s+хуже|ухудш))"


def measures_in(text: str) -> list[str]:
    found = []
    for num in re.findall(r"\b[MМмm]\s?(\d{1,2})\b", text):
        code = f"M{int(num)}"
        if code not in found and 1 <= int(num) <= 14:
            found.append(code)
    low = text.lower()
    for code, pattern in MEASURE_WORDS.items():
        if code not in found and re.search(pattern, low):
            found.append(code)
    return found


def districts_in(text: str) -> list[str]:
    low = text.lower()
    return [name for name, stem in DISTRICT_STEMS.items() if re.search(stem, low)]


def indicators_in(text: str) -> list[str]:
    low = text.lower()
    return [code for code, pattern in INDICATOR_WORDS.items() if re.search(pattern, low)]


def _clauses(text: str) -> list[str]:
    return [c.strip() for c in re.split(r"[.;!?\n,]|\s(?:но|а|при\s+этом)\s", text.lower()) if c and c.strip()]


def parse_request(text: str, plan: list[dict] | None = None) -> dict:
    """Поручение пользователя → структурные условия поиска. Пустой dict — условий нет."""
    plan = plan or []
    where = {p["measure"]: p.get("district") for p in plan}
    req: dict = {}
    low = text.lower()

    for clause in _clauses(text):
        if not re.search(r"бюджет|потрат|трат|стоим|дороже|денег|единиц|максимум", clause):
            continue
        budget = (re.search(r"бюджет\w*\s+(?:в\s+)?(\d{2,3})\b", clause)
                  or re.search(r"(?:не\s+больше|не\s+дороже|максимум|в\s+пределах)\s+(\d{2,3})\b", clause)
                  or re.search(r"потрат\w*\s+(?:до\s+)?(\d{2,3})\b", clause))
        if budget and 10 <= int(budget.group(1)) <= 100:
            req["max_budget"] = int(budget.group(1))
            break
    floor = re.search(r"(?:ни\s+один\s+район|все\s+район\w*|каждый\s+район)\D{0,30}?(?:не\s+ниже|выше|от|до)\s+(\d{2})",
                      low)
    if floor:
        req["min_district_d"] = float(floor.group(1))

    keep, exclude, protect = [], [], []
    for clause in _clauses(text):
        ms, ds, inds = measures_in(clause), districts_in(clause), indicators_in(clause)
        if re.search(_PROTECT, clause) and inds:
            for d in ds or []:
                for k in inds:
                    protect.append({"district": d, "indicator": k})
            continue
        if re.search(_KEEP, clause) and ms:
            for m in ms:
                district = where.get(m) if m in where else (ds[0] if ds else None)
                keep.append({"measure": m, "district": district})
            continue
        if re.search(_EXCLUDE, clause) and ms:
            exclude += [m for m in ms if m not in exclude]
    if keep:
        req["keep"] = keep
    if exclude:
        req["exclude"] = exclude
    if protect:
        req["protect"] = protect
    lift = re.search(r"(подними|подтяни|вытяни|максимально\s+подними)\w*\s+(\w+)", low)
    if lift:
        ds = districts_in(lift.group(2))
        if ds:
            req["maximize"] = ds[0]
    return req
