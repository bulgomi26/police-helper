"""에이전트가 쓰는 도구 6개: 함수 + LLM에 넘길 스키마(OpenAI tools 형식)."""
import json

from .analyze_message import analyze_message
from .assess_risk import assess_risk
from .check_official_contact import check_official_contact
from .draft_document import draft_document
from .get_action_plan import get_action_plan
from .get_strategy_card import get_strategy_card
from .report_situation import AGENCIES, ROLES, STATUSES, report_situation
from .search_law import search_law

FUNCTIONS = {
    "analyze_message": analyze_message,
    "check_official_contact": check_official_contact,
    "search_law": search_law,
    "get_strategy_card": get_strategy_card,
    "get_action_plan": get_action_plan,
    "assess_risk": assess_risk,
    "draft_document": draft_document,
    "report_situation": report_situation,
}

SIGNAL_IDS = ["suspect_status", "testimony_only", "unverified_evidence", "pressure_remarks",
              "unknown_charge", "serious_charge", "status_shift"]
LAW_TAGS = ["출석요구", "연기", "일정", "피의자", "참고인", "변호인", "피의자신문",
            "진술거부권", "권리고지", "조서열람", "조서", "수정", "영상녹화", "녹음",
            "수사기관", "검사", "사칭"]


def _fn(name, description, properties, required):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


TOOLS = [
    _fn(
        "report_situation",
        "첫 답변용: 사용자의 설명을 읽고 이해한 상황을 정리해 넘긴다. 사용자가 말한 내용만 쓰고, 말하지 않은 건 비우거나 '모름'.",
        {
            "role": {"type": "string", "enum": ROLES, "description": "사용자 본인의 신분"},
            "agency": {"type": "string", "enum": AGENCIES, "description": "연락한 기관"},
            "status": {"type": "string", "enum": STATUSES},
            "summary": {"type": "string", "description": "사용자 상황을 쉬운 말로 2문장 요약. 법 조문·판단·전화번호 넣지 말 것"},
            "case_type": {"type": "string", "description": "사건 종류 (예: 중고거래 사기). 모르면 빈칸"},
            "date": {"type": "string", "description": "출석하라는 날짜 (예: 다음 주 화요일). 모르면 빈칸"},
            "reason": {"type": "string", "description": "날짜를 못 맞추는 이유 한 단어 (예: 시험). 없으면 빈칸"},
            "evidence": {"type": "string", "description": "수사관이 말한 증거 (예: CCTV). 없으면 빈칸"},
            "signals": {"type": "array", "items": {"type": "string", "enum": SIGNAL_IDS},
                        "description": "변호사 상담 필요도 신호. 사용자 본인에 대해 글에서 확인되는 것만: suspect_status(본인이 피의자), "
                                       "testimony_only(물증 없이 진술이 핵심), unverified_evidence(수사관이 증거를 말했지만 내용 모름), "
                                       "pressure_remarks(수사관의 예단·압박 발언), unknown_charge(혐의 내용을 모름), "
                                       "serious_charge(본인 혐의가 성범죄·사기 등 무거운 죄명), status_shift(참고인인데 나를 의심하는 질문)"},
            "sex_crime": {"type": "boolean", "description": "본인이 성범죄 피의자로 연락받았으면 true"},
        },
        ["role", "agency", "status", "summary"],
    ),
    _fn(
        "analyze_message",
        "받은 문자·메일·통화 내용에서 기관명·번호·링크·신분 표현과 사칭 신호를 뽑는다. 연락 내용을 처음 들으면 가장 먼저 호출.",
        {"text": {"type": "string", "description": "받은 연락 원문이나 통화 메모"}},
        ["text"],
    ),
    _fn(
        "check_official_contact",
        "기관명으로 공식 확인 단계(verify_steps)를 가져온다. 없는 조직명이면 알려 준다.",
        {
            "org_name": {"type": "string", "description": "연락에 나온 기관·부서명"},
            "phone": {"type": "string", "description": "사용자가 직접 말한 번호만. 말하지 않았으면 빈 문자열"},
        },
        ["org_name"],
    ),
    _fn(
        "search_law",
        "상황에 맞는 조문을 찾는다. 근거는 이 결과의 조문만 쓴다.",
        {
            "query": {"type": "string", "description": "찾을 내용 (예: 출석 연기)"},
            "tags": {"type": "array", "items": {"type": "string", "enum": LAW_TAGS}},
        },
        ["query"],
    ),
    _fn(
        "get_strategy_card",
        "선택지별 장단점 카드. reference_alone=참고인 조사에 혼자 갈지, recording=녹음, silence=진술거부권.",
        {"card_id": {"type": "string", "enum": ["reference_alone", "recording", "silence"]}},
        ["card_id"],
    ),
    _fn(
        "assess_risk",
        "확인된 위험 신호로 변호사 상담 필요도(🟢🟡🔴)를 정한다. 신호는 사용자 본인이 받는 혐의 기준이며, "
        "참고인·피해자에게는 피의자용 신호(serious_charge, testimony_only 등)를 넣지 않는다.",
        {
            "signal_ids": {
                "type": "array",
                "items": {"type": "string", "enum": SIGNAL_IDS},
                "description": "suspect_status=피의자 출석요구, testimony_only=진술만 있는 사건, unverified_evidence=말한 증거를 확인 못 함, "
                "pressure_remarks=예단·압박 발언, unknown_charge=혐의 내용 모름, serious_charge=무거운 죄명, status_shift=참고인 조사가 추궁으로 바뀜",
            },
            "sex_crime_suspect": {"type": "boolean"},
        },
        ["signal_ids"],
    ),
    _fn(
        "get_action_plan",
        "신분과 상담 필요도에 맞는 권하는 순서. 답변의 블록 순서를 이 steps에 맞춘다.",
        {
            "role": {"type": "string", "description": "피의자, 참고인, 피해자, 모름 중 하나"},
            "risk_level": {"type": "string", "enum": ["green", "yellow", "red"]},
        },
        ["role"],
    ),
    _fn(
        "draft_document",
        "수사관에게 할 말이나 목록. postpone_request=날짜 미루기, ask_case_info=사건·신분·증거 확인, "
        "prep_list=출석 준비(role 필요), consult_request=132 상담 신청, call_checklist=통화 메모, interview_memo=조사 당일 메모. 실명은 넣지 않는다.",
        {
            "doc_type": {"type": "string",
                         "enum": ["postpone_request", "ask_case_info", "prep_list", "consult_request", "call_checklist", "interview_memo"]},
            "fields": {
                "type": "object",
                "description": "대화에서 확인된 값만",
                "properties": {k: {"type": "string"} for k in
                               ["station", "officer", "date", "reason", "alt_dates", "case_no", "role", "evidence", "case_type"]},
            },
        },
        ["doc_type"],
    ),
]


def run_tool(name: str, arguments: str | dict) -> dict:
    """LLM이 요청한 도구를 실행한다. 잘못된 요청도 예외 대신 오류 내용을 돌려줘 모델이 고칠 수 있게 한다."""
    if name not in FUNCTIONS:
        return {"error": f"없는 도구: {name}"}
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
    except json.JSONDecodeError as e:
        return {"error": f"인자 JSON 오류: {e}"}
    try:
        return FUNCTIONS[name](**args)
    except TypeError as e:
        return {"error": f"인자 오류: {e}"}
