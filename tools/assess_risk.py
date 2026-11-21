"""체크리스트 신호를 집계해 상담 필요도 안내 단계를 정한다 (규칙 기반)."""
from .data_loader import load
from .search_law import get_articles


def assess_risk(signal_ids: list, sex_crime_suspect: bool = False) -> dict:
    data = load("risk_signals")
    by_id = {s["id"]: s for s in data["signals"]}
    matched = [by_id[i] for i in dict.fromkeys(signal_ids) if i in by_id]
    unknown = [i for i in signal_ids if i not in by_id]
    count = len(matched)

    level = next(l for l in data["levels"] if l["min"] <= count <= l["max"])
    if sex_crime_suspect:
        level = next(l for l in data["levels"] if l["id"] == "red")

    return {
        "count": count,
        "total_signals": len(data["signals"]),
        "level": level["id"],
        "emoji": level["emoji"],
        "label": level["label"],
        "recommendation": level["recommendation"],
        "sex_crime_override": sex_crime_suspect,
        "matched": [
            {"id": s["id"], "label": s["label"], "meaning": s["meaning"], "basis": get_articles(s["basis"])}
            for s in matched
        ],
        "unchecked": [s["label"] for s in data["signals"] if s not in matched],
        "unknown_ids": unknown,
        "notice": "체크리스트에 따른 안내이며 법률 판단이 아닙니다.",
    }
