import json
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "akim.json"


@lru_cache
def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache
def measures_by_id():
    return {m["id"]: m for m in load_data()["measures"]}


def get_measure(measure_id):
    measure = measures_by_id().get(measure_id)
    if measure is None:
        raise KeyError(f"неизвестное мероприятие: {measure_id}")
    return measure


@lru_cache
def districts_by_name():
    return {d["name"]: d for d in load_data()["districts"]}


def get_district(name):
    district = districts_by_name().get(name)
    if district is None:
        raise KeyError(f"неизвестный район: {name}")
    return district


@lru_cache
def district_names():
    return tuple(d["name"] for d in load_data()["districts"])


@lru_cache
def indicator_codes():
    return tuple(i["code"] for i in load_data()["indicators"])


@lru_cache
def indicator_weights():
    return {i["code"]: i["weight"] for i in load_data()["indicators"]}


@lru_cache
def direction_names():
    return {d["code"]: d["name"] for d in load_data()["directions"]}
