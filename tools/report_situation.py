"""AI가 사용자의 자유로운 설명을 읽고 상황을 정리해 넘기는 도구.

첫 답변에서 AI는 이 도구로 '이해한 내용'(신분·기관·상태·사유·요약)을 구조화해 넘기고,
법률·절차 안내 본문은 검증된 데이터로 앱이 만든다. (AI는 이해·분류·요약, 법률 내용은 검증 데이터)
"""
ROLES = ["피의자", "참고인", "피해자", "모름"]
AGENCIES = ["경찰", "공소청", "중수청", "모름"]
STATUSES = ["출석_요청", "조사_중_또는_체포", "피해_신고_상담", "기타"]


SIGNAL_IDS = ["suspect_status", "testimony_only", "unverified_evidence", "pressure_remarks",
              "unknown_charge", "serious_charge", "status_shift"]


def report_situation(role="모름", agency="모름", status="출석_요청", summary="", case_type="", date="",
                     reason="", evidence="", signals=None, sex_crime=False,
                     followups=None):
    clean = lambda v, ok, d: v if v in ok else d  # noqa: E731
    return {
        "role": clean(role, ROLES, "모름"),
        "agency": clean(agency, AGENCIES, "모름"),
        "status": clean(status, STATUSES, "기타"),
        "summary": (summary or "").strip()[:300],
        "case_type": (case_type or "").strip()[:30],
        "date": (date or "").strip()[:30],
        "reason": (reason or "").strip()[:20],
        "evidence": (evidence or "").strip()[:20],
        "signals": [x for x in (signals or []) if x in SIGNAL_IDS],
        "sex_crime": bool(sex_crime) and role == "피의자",
        "followups": [x for x in (followups or []) if isinstance(x, str)][:3],  # 검증은 suggest_questions에서
    }
