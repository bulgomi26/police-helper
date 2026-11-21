"""선택지·판단 기준 카드를 돌려준다. 카드 하나에 그 주제의 관련 내용이 모두 들어 있다."""
from .data_loader import load
from .search_law import get_articles


def get_strategy_card(card_id: str) -> dict:
    cards = {c["id"]: c for c in load("strategy_cards")["cards"]}
    card = cards.get(card_id)
    if not card:
        return {"error": f"알 수 없는 카드: {card_id}", "available": list(cards)}
    out = dict(card)
    out["basis_articles"] = get_articles(card.get("basis", []))
    out["notice"] = "선택지와 근거를 보여 드리는 것이며, 결정은 본인이 합니다. 개별 사건 판단은 변호사·법률구조공단(132)에 확인하세요."
    return out
