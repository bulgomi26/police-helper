"""신분과 상담 필요도에 맞는 '일반적으로 권하는 순서'를 돌려준다 (규칙 기반)."""
from .data_loader import load


def get_action_plan(role: str = "", risk_level: str = "") -> dict:
    data = load("action_plans")
    plans = {p["id"]: p for p in data["plans"]}
    role = (role or "").strip()
    role_unknown = not any(r in role for r in ("피의자", "참고인", "피해자"))
    is_suspect = "피의자" in role
    risky = risk_level in ("yellow", "red")
    # 신분을 모르면 위험을 낮춰 보지 않도록 피의자 기준 순서로 안내한다
    plan = plans["suspect_or_risky"] if (is_suspect or risky or role_unknown) else plans["reference_low"]
    steps = []
    for i, st in enumerate(plan["steps"], 1):
        steps.append({
            "order": i,
            "block": st["block"],
            "block_title": data["block_titles"][st["block"]],
            "text": st["text"],
            "basis": st.get("basis") or data.get("block_guides", {}).get(st["block"], {}).get("basis"),
            "prepare": data.get("block_guides", {}).get(st["block"], {}).get("prepare", []),
            "how": data.get("block_guides", {}).get(st["block"], {}).get("how", []),
            "doc_type": data.get("block_guides", {}).get(st["block"], {}).get("doc_type"),
            "basis_note": data.get("block_guides", {}).get(st["block"], {}).get("basis_note", ""),
        })
    return {
        "plan_id": plan["id"],
        "role_unknown": role_unknown,
        "title": plan["title"],
        "steps": steps,
        "notice": "많은 경우에 권하는 일반적인 순서이며, 개별 사건 판단은 변호사·법률구조공단(132)에 확인하세요.",
    }
