from collections import Counter

from .data import direction_names, district_names, load_data, measures_by_id


def normalize_plan(plan):
    normalized = []
    for item in plan:
        measure = str(item.get("measure", "")).strip().upper()
        district = item.get("district")
        if district is not None:
            district = str(district).strip()
            if district == "":
                district = None
        normalized.append({"measure": measure, "district": district})
    return normalized


def validate(plan):
    items = normalize_plan(plan)
    data = load_data()
    measures = measures_by_id()
    names = set(district_names())
    directions = direction_names()
    violations = []

    if len(items) != data["decisions"]:
        violations.append({
            "code": "count",
            "message": f"Нужно ровно {data['decisions']} решений, указано {len(items)}",
            "measures": [item["measure"] for item in items],
        })

    ids = [item["measure"] for item in items]
    for measure_id, count in Counter(ids).items():
        if count > 1:
            violations.append({
                "code": "duplicate",
                "message": f"Мероприятие {measure_id} выбрано более одного раза",
                "measures": [measure_id],
            })

    for item in items:
        if item["measure"] not in measures:
            violations.append({
                "code": "unknown_measure",
                "message": f"Неизвестное мероприятие: {item['measure']}",
                "measures": [item["measure"]],
            })

    known_items = [item for item in items if item["measure"] in measures]

    for item in known_items:
        measure_id = item["measure"]
        district = item["district"]
        scope = measures[measure_id]["scope"]
        if district is not None and district not in names:
            violations.append({
                "code": "unknown_district",
                "message": f"{measure_id}: неизвестный район «{district}»",
                "measures": [measure_id],
            })
            continue
        if scope == "district" and district is None:
            violations.append({
                "code": "district_required",
                "message": f"{measure_id}: нужно указать район",
                "measures": [measure_id],
            })
        elif scope == "city" and district is not None:
            violations.append({
                "code": "district_not_allowed",
                "message": f"{measure_id}: городская мера, район указывать не нужно",
                "measures": [measure_id],
            })

    budget = data["budget"]
    total_cost = sum(measures[item["measure"]]["cost"] for item in known_items)
    if total_cost > budget:
        violations.append({
            "code": "budget",
            "message": f"Бюджет превышен: {total_cost} из {budget}",
            "measures": [item["measure"] for item in known_items],
        })

    max_per_direction = data["max_per_direction"]
    by_direction = {}
    for item in known_items:
        direction = measures[item["measure"]]["direction"]
        by_direction.setdefault(direction, []).append(item["measure"])
    for direction, measure_ids in by_direction.items():
        if len(measure_ids) > max_per_direction:
            violations.append({
                "code": "direction_limit",
                "message": (
                    f"Больше {max_per_direction} мер в направлении "
                    f"«{directions.get(direction, direction)}»: {len(measure_ids)}"
                ),
                "measures": measure_ids,
            })

    district_by_measure = {item["measure"]: item["district"] for item in known_items}
    for conflict in data["conflicts"]:
        a, b = conflict["pair"]
        if a not in district_by_measure or b not in district_by_measure:
            continue
        if conflict["same_district_only"]:
            da, db = district_by_measure[a], district_by_measure[b]
            if da is not None and db is not None and da == db:
                violations.append({
                    "code": "conflict",
                    "message": f"{a} и {b} нельзя в одном районе: {conflict['reason']}",
                    "measures": [a, b],
                })
        else:
            violations.append({
                "code": "conflict",
                "message": f"{a} и {b} несовместимы: {conflict['reason']}",
                "measures": [a, b],
            })

    return violations
