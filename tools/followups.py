"""이어서 물어볼 질문(답변 아래 버튼).

버튼 하나 = 카드 하나. 한 주제를 잘게 쪼개 하나씩 묻게 하지 않는다 (카드를 열면 관련 내용이 한 번에 나온다).
AI는 suggest_questions로 지금 대화와 관련된 다른 카드를 고르고, 관련된 게 없으면 고르지 않는다 → 버튼이 나오지 않는다.
AI가 고르지 못했을 때(기본 안내 모드 등)는 데이터에 적어 둔 관련 카드(related)와 신분별 기본값으로 채운다.
"""
from .data_loader import load

MAX_SUGGEST = 3

# 첫 답변에서 신분별로 보여 줄 카드 (AI가 고르지 못했을 때). 피해자·조사 중·사칭 의심은 없음
ROLE_DEFAULTS = {
    "피의자": ["silence", "recording"],
    "모름": ["silence", "recording"],
    "참고인": ["reference_alone", "recording"],
}


def catalog():
    """[{id, q, card, related}] — 카드마다 질문 하나"""
    return [{"id": c["id"], "q": c["ask"], "card": c["id"], "related": c.get("related", [])}
            for c in load("strategy_cards")["cards"] if c.get("ask")]


def question_ids():
    return [x["id"] for x in catalog()]


def find_by_text(text):
    """버튼으로 들어온 질문이면 해당 카드를 돌려준다 (기본 안내 모드에서도 같은 카드를 보여 주려고)"""
    t = (text or "").strip()
    return next((x for x in catalog() if x["q"] == t), None)


def suggest_questions(ids=None):
    """AI가 고른 카드 id를 검증해 버튼 문장으로 바꾼다. 없는 id는 버린다. 빈 목록이면 버튼이 나오지 않는다."""
    by_id = {x["id"]: x for x in catalog()}
    picked = list(dict.fromkeys(i for i in (ids or []) if i in by_id))
    return {"questions": [{"id": i, "q": by_id[i]["q"]} for i in picked[:MAX_SUGGEST]]}


def default_ids(role=None, shown_card=None):
    """규칙으로 고르기: 카드를 보여 줬으면 그 카드와 관련된 카드만, 첫 답변이면 신분별 기본값."""
    if shown_card:
        card = next((x for x in catalog() if x["id"] == shown_card), None)
        return [i for i in (card["related"] if card else []) if i != shown_card]
    return list(ROLE_DEFAULTS.get(role or "", []))
