"""상황 태그·키워드로 핵심 조문을 찾는다 (로컬 JSON)."""
from datetime import date

from .data_loader import load

LAW_SEARCH_URL = "https://www.law.go.kr/법령/"


def _status(art):
    """in_force(시행 중) 또는 upcoming(시행 예정)."""
    eff = art.get("effective")
    if eff and date.fromisoformat(eff) > date.today():
        return "upcoming"
    return "in_force"


def search_law(query: str = "", tags: list | None = None, limit: int = 3) -> dict:
    tags = tags or []
    words = [w for w in query.replace(",", " ").split() if len(w) >= 2]
    scored = []
    for art in load("laws")["articles"]:
        score = 3 * sum(t in art["tags"] for t in tags)
        hay = " ".join([art["title"], art["summary"], " ".join(art["tags"])])
        score += sum(w in hay for w in words)
        if score > 0:
            scored.append((score, art))
    scored.sort(key=lambda x: -x[0])
    results = [
        {
            "id": a["id"],
            "law": a["law"],
            "article": a["article"],
            "title": a["title"],
            "summary": a["summary"],
            "status": _status(a),
            "effective": a.get("effective"),
            "verified": a["verified"],
            "source_url": LAW_SEARCH_URL + a["law"].replace(" ", ""),
        }
        for _, a in scored[:limit]
    ]
    return {
        "query": query,
        "tags": tags,
        "results": results,
        "found": len(results),
        "rule": "status가 upcoming인 조문은 아직 시행 전이므로 '시행 예정'이라고 밝힐 것",
    }


def get_articles(ids):
    by_id = {a["id"]: a for a in load("laws")["articles"]}
    return [
        {
            "id": i,
            "label": f"{by_id[i]['law']} {by_id[i]['article']} ({by_id[i]['title']})",
            "verified": by_id[i]["verified"],
            "status": _status(by_id[i]),
        }
        for i in ids
        if i in by_id
    ]
