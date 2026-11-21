"""첫 답변 만들기: AI가 상황을 이해·정리하고, 안내 본문은 검증된 데이터로 조립한다.

1) AI(LLM)가 사용자의 자유로운 설명을 읽고 report_situation 도구로 신분·기관·상태·날짜·사유·요약을 넘긴다. (모델 호출 1번)
2) 앱이 그 정리와 규칙 도구(사칭 점검, 기관 확인 절차, 권하는 순서, 말할 문장, 선택지 카드)로 답변을 만든다.
→ 법 조문·절차·전화번호는 AI가 지어낼 수 없고, AI는 '이해와 개인화'를 맡는다.
두 번째 질문부터는 AI가 도구를 골라 자유롭게 답한다 (agent.run).
"""
from fallback import basic_answer


def first_answer(agent, history, user_text):
    """반환: (답변, 이벤트, AI가 정리한 상황 dict)"""
    _, events, _ = agent.run(history, forced_tools=["report_situation"], stop_after_forced=True)
    slots = next((e["result"] for e in events if e["tool"] == "report_situation" and "error" not in e["result"]), None)
    if slots is None:
        raise RuntimeError("AI가 상황 정리(report_situation)를 돌려주지 않았습니다.")
    reply, all_events = basic_answer(user_text, slots=slots, events=events)
    return reply, all_events, slots
