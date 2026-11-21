"""상황별로 '이렇게 말해 보세요' 문장과 메모 양식을 만든다 (템플릿).

출석요구는 대부분 전화로 오고 전화로 답하므로, 문장은 말하는 투로 쓴다. (문자로 보내도 어색하지 않게)
"""

TEMPLATES = {
    # 출석 날짜를 미루고 싶을 때
    "postpone_request": (
        "안녕하세요, {station} {officer} 수사관님 맞으신가요? {date} 출석 건으로 연락드렸습니다.\n"
        "그날은 {reason} 때문에 출석이 어렵습니다. 혹시 {alt_dates} 중으로 조정이 가능할까요?\n"
        "그리고 준비를 위해 여쭤보고 싶은데, 어떤 사건이고 제가 어떤 신분(참고인인지 피의자인지)으로 가는 건지 알려주실 수 있을까요?"
    ),
    # 출석 날짜를 미루고 싶을 때 — 문자로 보낼 때
    "postpone_request_sms": (
        "안녕하세요, {station} {officer} 수사관님. {date} 출석 요청을 받은 사람입니다.\n"
        "그날은 {reason} 때문에 출석이 어려워 일정 조정을 부탁드립니다.\n"
        "{alt_dates}에는 출석할 수 있습니다.\n"
        "준비를 위해 어떤 사건인지, 제가 어떤 신분(참고인/피의자)으로 출석하는지도 알려주시면 감사하겠습니다."
    ),
    # 사건 내용·신분·출석요구서를 확인하고 싶을 때
    "ask_case_info": (
        "안녕하세요, {station} {officer} 수사관님. 출석 요청 건으로 연락드렸습니다.\n"
        "제가 어떤 사건으로, 어떤 신분으로 조사를 받는 건지 정확히 알고 싶습니다.\n"
        "혐의 요지가 적힌 출석요구서를 받아볼 수 있을까요? 사건번호도 알려주시면 감사하겠습니다."
    ),
    # 출석 전에 준비할 것
    "prep_list": (
        "- □ 신분증\n"
        "- □ 출석요구서나 출석 요청 문자 (받았다면)\n"
        "- □ 사건 관련 자료: 대화 내용, 거래 내역, 사진 등 (원본은 지우지 말고 그대로 보관)\n"
        "- □ 일어난 일을 날짜·시간 순서로 정리한 메모 (기억이 확실한 것과 아닌 것 구분)\n"
        "- □ 조사 때 물어볼 것: 내 신분이 무엇인지, 어떤 사건인지\n"
        "{role_extra}"
    ),
    # 대한법률구조공단(132)에 상담을 신청할 때
    "consult_request": (
        "안녕하세요. 경찰에서 {role} 신분으로 출석 요청을 받았는데, 출석 전에 법률 상담을 받고 싶습니다.\n"
        "{case_type} 관련 사건이고, 출석 예정일은 {date}입니다. 상담을 신청할 수 있을까요?"
    ),
    # 통화하면서 메모할 것
    "call_checklist": (
        "- □ 기관·부서·수사관 이름: {station} {officer}\n"
        "- □ 사건번호: {case_no}\n"
        "- □ 내 신분 (피의자/참고인/피해자): {role}\n"
        "- □ 어떤 사건인지 (고소인, 혐의 요지)\n"
        "- □ 출석 일시·장소: {date}\n"
        "- □ 가져갈 자료\n"
        "- □ 통화 후 182에 전화해 수사관 소속·이름이 맞는지 확인했는가"
    ),
    # 조사 당일 메모 양식
    "interview_memo": (
        "- 조사 일시: {date}  · 장소: {station}\n"
        "- 조사관: {officer}  · 신분: {role}\n"
        "- 진술거부권·변호인 조력 안내를 받았나: □ 예 □ 아니오\n"
        "- 시작 / 휴식 / 종료 시각:\n"
        "- 주요 질문과 내 답변:\n"
        "- 자료 확인 후 답하겠다고 한 질문:\n"
        "- 조서를 읽고 고쳐 달라고 한 부분:\n"
        "- 부당하다고 느낀 말 (시각, 들은 그대로):"
    ),
}

ROLE_EXTRA = {
    "피의자": "- □ 변호사 상담을 받을지 출석 전에 정하기 (비용이 부담되면 대한법률구조공단 132)\n"
              "- □ 조사 시작 때 진술거부권·변호인 조력 안내를 받는지 확인하기",
    "참고인": "- □ 질문이 내 잘못을 묻는 쪽으로 바뀌면, 내 신분이 바뀐 것인지 물어보기",
}

LABELS = {
    "consult_request": "132에 상담을 신청할 때",
    "prep_list": "출석 전에 준비할 것",
    "postpone_request": "출석 날짜를 미루고 싶을 때",
    "postpone_request_sms": "출석 날짜를 미루고 싶을 때 (문자)",
    "ask_case_info": "사건 내용·신분을 확인하고 싶을 때 — 이렇게 말해 보세요",
    "call_checklist": "통화하면서 메모할 것",
    "interview_memo": "조사 당일 메모 양식",
}

DEFAULTS = {
    "station": "○○경찰서",
    "officer": "○○○",
    "date": "○월 ○일",
    "reason": "개인 일정",
    "alt_dates": "○일이나 ○일",
    "case_no": "",
    "role": "",
    "evidence": "",
    "case_type": "○○",
}


def draft_document(doc_type: str, fields: dict | None = None) -> dict:
    if doc_type not in TEMPLATES:
        return {"error": f"알 수 없는 종류: {doc_type}", "available": list(TEMPLATES)}
    values = {**DEFAULTS, **{k: v for k, v in (fields or {}).items() if v}}
    if doc_type == "consult_request" and not values.get("role"):
        values["role"] = "○○"
    values["role_extra"] = next((t for k, t in ROLE_EXTRA.items() if k in values.get("role", "")), "")
    text = TEMPLATES[doc_type].format(**values)
    if doc_type == "ask_case_info" and values.get("evidence"):
        # 수사관이 증거를 언급했을 때만 묻는다
        text += f"\n그리고 말씀하신 {values['evidence']}에 대해서도, 어떤 내용인지 확인할 수 있는지 여쭤보고 싶습니다."
    out = {
        "doc_type": doc_type,
        "label": LABELS[doc_type],
        "text": text,
        "note": "○ 부분은 실제 내용으로 바꾸세요. 실명·주민번호 등은 이 서비스에 입력하지 마세요.",
    }
    if doc_type == "postpone_request":
        # 날짜 조정은 전화로도, 문자로도 할 수 있어 두 버전을 함께 준다
        out["versions"] = [
            {"channel": "📞 전화로 말할 때", "text": out["text"]},
            {"channel": "💬 문자로 보낼 때", "text": TEMPLATES["postpone_request_sms"].format(**values),
             "tip": "문자는 공식 번호(182·110)로 확인한 수사관 번호로 보내세요. 이름은 보낼 때 직접 적으세요."},
        ]
    return out
