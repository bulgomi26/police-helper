"""AI(LLM)를 쓸 수 없을 때의 기본 안내.

사칭 점검·확인 단계·권하는 순서·말할 문장·전략 카드는 모두 규칙 기반 도구라
LLM 없이도 같은 형식의 안내를 만들 수 있다. (API 한도 초과, 키 없음, 네트워크 오류 대비)
"""
import re

from tools import run_tool
from tools.followups import default_ids, find_by_text
from tools.data_loader import load

# 이미 조사실에 있거나 체포된 상황 ('체포영장' 같은 사칭 문구와 구분하려고 상태를 나타내는 말만 잡는다)
IN_CUSTODY_RE = re.compile(
    r"조사\s*(?:받는|받고\s*있는)?\s*중|조사받고\s*있|조사실(?:에|인데|이에요)|체포(?:됐|되었|당했|된\s*상태|돼서)|"
    r"연행(?:됐|되었|당했)|유치장|구속(?:됐|되었)|경찰서에\s*(?:잡혀|붙잡혀)")
REASON_WORDS = ["시험", "출근", "근무", "수업", "출장", "병원", "면접", "아르바이트", "알바", "여행"]
EVIDENCE_WORDS = ["CCTV", "영상", "녹취", "사진", "대화 내용", "카톡", "문자 내역", "계좌 내역"]
VICTIM_RE = re.compile(r"피해자|고소인|고소하고\s*싶|신고하고\s*싶|사기를?\s*당|피해를?\s*당")

CIRCLED = "①②③④⑤"


SHORT_LAW = {"검사와 사법경찰관의 상호협력과 일반적 수사준칙에 관한 규정": "수사준칙"}


def _law_line(law_id, note=""):
    arts = {a["id"]: a for a in load("laws")["articles"]}
    a = arts.get(law_id)
    if not a:
        return ""
    text = note or a["summary"].split(". ")[0].rstrip(".")
    return f"근거: {SHORT_LAW.get(a['law'], a['law'])} {a['article']} — {text}"


def _tips(tips):
    """'이럴 땐?' 접기: 화면에서 눌러야 펼쳐진다 (❓ 질문 :: 답 형식, app.safe_md가 변환)"""
    return [f"❓ {t['q']} :: {t['a']}" for t in tips or []]


def _quote(text):
    return "\n".join("> " + line for line in text.splitlines())


SERIOUS_WORDS = ["성범죄", "성추행", "성폭력", "강제추행", "불법촬영", "몰카", "사기", "마약", "폭행", "보이스피싱"]
SEX_WORDS = ["성범죄", "성추행", "성폭력", "강제추행", "불법촬영", "몰카", "화장실"]


def _risk_signals(user_text, role, slots):
    """AI가 넘긴 신호가 있으면 그것을, 없으면 글에서 규칙으로 찾는다."""
    if slots.get("signals"):
        return slots["signals"], slots.get("sex_crime", False)
    sig = []
    if role == "피의자":
        sig.append("suspect_status")
    if not slots.get("case_type") and not any(w in user_text for w in SERIOUS_WORDS):
        sig.append("unknown_charge")
    if slots.get("evidence") or any(w in user_text for w in EVIDENCE_WORDS):
        sig.append("unverified_evidence")
    if role == "피의자" and any(w in user_text for w in SERIOUS_WORDS):
        sig.append("serious_charge")
    return sig, role == "피의자" and any(w in user_text for w in SEX_WORDS)


AGENCY_ORG = {"경찰": "경찰서", "공소청": "공소청", "중수청": "중수청"}


def basic_answer(user_text, slots=None, events=None):
    """(답변 마크다운, 도구 이벤트 목록)을 돌려준다. 이벤트 형식은 에이전트와 같다.

    slots: AI가 report_situation으로 넘긴 상황 정리. 있으면 규칙 추출보다 우선한다 (AI 첫 답변 조립).
    없으면 규칙으로만 만든다 (기본 안내 모드).
    """
    events = list(events or [])
    slots = slots or {}

    def call(name, args):
        result = run_tool(name, args)
        events.append({"tool": name, "args": args, "result": result})
        return result

    prior = {e["tool"]: e["result"] for e in events}
    an = prior.get("analyze_message") or call("analyze_message", {"text": user_text})
    ex = an["extracted"]
    org = (ex["fake_orgs"] or ex["orgs"] or [AGENCY_ORG.get(slots.get("agency"), "경찰서")])[0]
    contact = call("check_official_contact", {"org_name": org, "phone": ""})

    # 사칭 의심: 경고와 확인 방법만
    if an["verdict"] == "high":
        lines = ["**지금 할 일**: 링크·파일을 열지 말고, 받은 번호로 다시 걸지 마세요.", "",
                 "### 사칭 가능성이 높아요",
                 "위 경고에 나온 신호가 보여요. 아래 순서로 공식 번호에서 직접 확인하세요.", ""]
        lines += [f"{i}. {s}" for i, s in enumerate(contact.get("verify_steps", []), 1)]
        lines += ["", "돈을 보내라거나 앱을 깔라고 했다면 바로 112에 신고하세요.",
                  "공식 번호로 확인해서 진짜였다면, 들은 내용을 다시 적어 주세요. 그다음 할 일을 안내해 드릴게요."]
        return "\n".join(lines), events

    if slots.get("status") == "조사_중_또는_체포" or IN_CUSTODY_RE.search(user_text):
        return _in_custody_answer(call), events

    roles = set(ex["roles"])
    if (slots.get("role") == "피해자" or slots.get("status") == "피해_신고_상담"
            or (VICTIM_RE.search(user_text) and "피의자" not in roles)):
        return _victim_answer(contact, call), events

    if slots.get("role") in ("피의자", "참고인"):
        role, mixed = slots["role"], False
    else:
        mixed = len(roles) > 1  # 신분이 여러 개 적혀 있으면 임의로 고르지 않는다
        role = roles.pop() if len(roles) == 1 else "모름"
    plan = call("get_action_plan", {"role": role})

    hotline = _hotline(contact)
    lines = [f"**지금 할 일**: 먼저 {hotline}에 전화해 연락한 사람이 진짜 수사관인지 확인하세요.", ""]

    lines += ["### 지금 상황"]
    if slots.get("summary"):
        lines += [slots["summary"], ""]
    lines.append(f"- 연락한 곳: {contact.get('short_name', org)}")
    if mixed:
        lines.append("- 내 신분: 글에 여러 신분이 함께 적혀 있어 확실하지 않아요 → 수사관에게 \"제 신분이 피의자인가요, 참고인인가요?\"라고 확인하세요")
    else:
        lines.append(f"- 내 신분: {role if role != '모름' else '아직 확인 전 → 수사관에게 확인하세요'}")
    lines.append("")

    lines += ["### 이 상황에서 권하는 순서", plan["title"], ""]
    for i, stp in enumerate(plan["steps"]):
        lines.append(f"- {CIRCLED[i]} {stp['text']}")  # 목록으로 써야 한 줄씩 보인다
    lines.append(f"\n_{plan['notice']}_")
    if plan.get("role_unknown"):
        lines.append("신분을 확인하기 전까지는 피의자 기준으로 안내드려요.")
    lines.append("")

    lines += ["### 먼저, 연락한 사람이 진짜 수사관인지 확인하기"]
    lines += [f"{i}. {s}" for i, s in enumerate(contact.get("verify_steps", []), 1)]
    talk = [(CIRCLED[i], stp) for i, stp in enumerate(plan["steps"]) if stp["block"] in ("postpone", "case_check")]
    if talk:
        lines += ["", "**확인되면, 그 통화 한 번에 같이 말하세요:**"]
        for num, stp in talk:
            what = "날짜를 미루고 싶다면" if stp["block"] == "postpone" else "무슨 사건인지 알고 싶다면"
            lines.append(f"- {what} → {num}")
        if len(talk) > 1:
            lines += ["", f"{talk[0][0]}과 {talk[1][0]}를 한 번에 말해도 돼요."]  # 빈 줄: 목록에 붙지 않게
    if contact.get("tips"):
        lines += [""] + _tips(contact["tips"])
    if contact.get("next_call_tip"):
        lines += ["", contact["next_call_tip"]]
    lines.append("")

    sig, sex = _risk_signals(user_text, role, slots)
    risk = call("assess_risk", {"signal_ids": sig, "sex_crime_suspect": sex})
    events[-1]["inlined"] = True  # 변호사 블록 안에 바로 보여 주므로 아래 카드로 또 띄우지 않는다

    for i, stp in enumerate(plan["steps"]):
        lines.append(f"### {CIRCLED[i]} {stp['block_title']}")
        if stp["block"] == "lawyer":
            lines.append(f"**지금 상황에서는: {risk['emoji']} {risk['label']}**")
            lines.append(risk["recommendation"])
            if risk["matched"]:
                lines.append("")
                lines.append("이렇게 안내하는 이유 (체크리스트에 해당하는 항목, 법률 판단 아님):")
                lines += [f"- {m['label']}" for m in risk["matched"]]
            if risk.get("sex_crime_override"):
                lines.append("- 성범죄 피의자 출석요구는 신호 개수와 관계없이 🔴로 안내해요.")
            lines += ["", "❓ 이럴 때는 꼭 상담받으세요 :: 수사관이 나를 의심하는 질문을 하거나, 증거가 있다고만 하고 내용을 안 알려 주거나, "
                      "처벌이 무거운 죄명(성범죄·사기 등)이라면 출석 전에 상담을 받으세요.", "",
                      "#### 상담받는 방법"]
        if stp["prepare"]:
            lines.append("**준비물**")
            lines += [f"- {x}" for x in stp["prepare"]]
            lines.append("")
        lines.append("**순서**")
        lines += [f"{j}. {x}" for j, x in enumerate(stp["how"], 1)]
        lines.append("")
        if stp.get("doc_type"):
            fields = {"role": role if role != "모름" else "",
                      "reason": slots.get("reason") or next((w for w in REASON_WORDS if w in user_text), ""),
                      "evidence": slots.get("evidence") or next((w for w in EVIDENCE_WORDS if w in user_text), ""),
                      "case_type": slots.get("case_type", ""),
                      "date": slots.get("date", "")}
            doc = call("draft_document", {"doc_type": stp["doc_type"], "fields": fields})
            if stp["doc_type"] == "prep_list":
                lines.append(doc["text"])
            elif doc.get("versions"):
                lines.append("**이렇게 말씀해 보세요**:")
                for v in doc["versions"]:
                    lines += [v["channel"], _quote(v["text"]), ""]
                    if v.get("tip"):
                        lines += [v["tip"], ""]
            else:
                lines += ["**이렇게 말씀해 보세요**:", _quote(doc["text"])]
            lines.append("")
        if stp.get("tips"):
            lines += _tips(stp["tips"]) + [""]
        law = _law_line(stp.get("basis"), stp.get("basis_note", ""))
        if law:
            lines += [law, ""]
    # 진술거부·녹음 같은 카드는 한 번에 다 보여 주지 않고, 이어서 물어볼 질문 버튼으로 연결한다
    # (AI가 상황을 정리하며 고른 질문이 있으면 그것을, 없으면 신분별 기본 질문)
    context = " ".join([user_text, slots.get("case_type", ""), slots.get("evidence", "")])
    rule_ids = default_ids(role, context=context, sex_crime=sex)
    call("suggest_questions", {"ids": slots.get("followups") or rule_ids})
    if not events[-1]["result"]["questions"]:
        events[-1]["result"] = run_tool("suggest_questions", {"ids": rule_ids})
    return "\n".join(lines), events


def _hotline(contact):
    steps = " ".join(contact.get("verify_steps", []))
    return "182(경찰민원콜센터)" if "182" in steps else "110(정부민원안내콜센터)"


def _in_custody_answer(call):
    """이미 조사 중이거나 체포된 상황: 형식 없이 지금 쓸 수 있는 권리 세 가지만."""
    lines = ["**지금 할 일**: 조사를 다시 시작하기 전에, 아래 세 가지를 수사관에게 말할 수 있어요.", "",
             "1. **변호인을 불러 조사에 참여하게 해 달라고 할 수 있어요.** \"변호인과 상의한 뒤에 조사를 받고 싶습니다.\"",
             "2. **진술을 거부해도 불이익이 없어요.** 모든 질문에, 또는 일부 질문에만 답하지 않을 수 있어요.",
             "3. **조서를 끝까지 읽고, 내 말과 다른 부분은 고쳐 달라고 할 수 있어요.**", ""]
    for law_id in ("cpa_243_2", "cpa_244_3", "cpa_244"):
        line = _law_line(law_id)
        if line:
            lines += [line, ""]
    lines += ["아는 변호사가 없으면 가족에게 변호인을 구해 달라고 부탁하거나, 대한법률구조공단(국번 없이 132)에 도움을 요청하세요.",
              "이 서비스는 출석 전 준비를 돕는 용도라, 조사 중에는 위 세 가지만 기억하세요."]
    return "\n".join(lines)


def _victim_answer(contact, call):
    """피해자·고소인: 진술하러 나오라는 연락이면 확인·날짜 조정만, 신고·고소 상담은 범위 밖."""
    hotline = _hotline(contact)
    doc = call("draft_document", {"doc_type": "postpone_request", "fields": {"role": "참고인"}})
    lines = [f"**지금 할 일**: 진술하러 오라는 연락이었다면, 먼저 {hotline}에 전화해 연락한 사람이 진짜 수사관인지 확인하세요.", "",
             "### 피해자로 연락을 받으셨군요",
             "이 서비스는 수사기관에서 출석 요청을 받은 사람을 위한 안내예요. 피해 신고나 고소 방법은 다루지 않아요.",
             "- 지금 위험하거나 범죄가 진행 중이면: **112**",
             "- 고소·피해 회복 등 법률 상담: **대한법률구조공단 132** (무료)", "",
             "### 진술 날짜가 맞지 않으면",
             "피의자가 아니어도 출석 날짜를 협의하고 미뤄 달라고 요청할 수 있어요. 새 날짜가 확정될 때까지는 원래 날짜를 지키세요.", ""]
    if doc.get("versions"):
        lines.append("**이렇게 말씀해 보세요**:")
        for v in doc["versions"]:
            lines += [v["channel"], _quote(v["text"]), ""]
    law = _law_line("rule_19", "연기를 요청하면 특별한 사정이 없는 한 출석 일시를 조정해야 한다 (피의자 외의 사람에게도 적용)")
    if law:
        lines.append(law)
    return "\n".join(lines)


FOLLOWUP_CARDS = [  # 위에서부터 먼저 맞는 것 (구체적인 말을 앞에)
    (("휴대폰", "핸드폰", "임의제출", "폰을"), "phone_submit"),
    (("조서", "서명"), "read_record"),
    (("심야", "밤늦게", "밤 늦게", "몇 시간", "오래 걸", "길어지"), "interview_time"),
    (("참고인인데 꼭", "참고인도 꼭", "참고인인데 안 가", "참고인은 안 가"), "reference_no_show"),
    (("출석 안 하", "안 가면", "안 나가면", "불출석", "출석하지 않"), "no_show"),
    (("녹음", "녹화", "기록"), "recording"),
    (("진술", "묵비", "거부", "말하지"), "silence"),
    (("혼자", "참고인", "동행", "같이 가"), "reference_alone"),
]


def _card_reply(card_id):
    result = run_tool("get_strategy_card", {"card_id": card_id})
    events = [{"tool": "get_strategy_card", "args": {"card_id": card_id}, "result": result}]
    ids = default_ids(shown_card=card_id)  # 이 카드와 관련된 다른 카드만. 없으면 버튼 없음
    events.append({"tool": "suggest_questions", "args": {"ids": ids}, "result": run_tool("suggest_questions", {"ids": ids})})
    return f"이 질문과 관련된 내용을 아래 카드로 정리했어요. ({result['title']})", events


def basic_followup(user_text):
    """두 번째 질문부터 AI를 쓸 수 없을 때: 질문에 맞는 전략 카드(항목)만 보여 준다."""
    hit = find_by_text(user_text)  # 답변 아래 질문 버튼으로 들어온 질문
    if hit:
        return _card_reply(hit["card"])
    for words, card_id in FOLLOWUP_CARDS:
        if any(w in user_text for w in words):
            return _card_reply(card_id)
    reply = ("지금은 기본 안내만 드릴 수 있어요. 앞의 안내에서 ①부터 차례로 진행하시고, "
             "판단이 필요한 부분은 대한법률구조공단(국번 없이 132)에 무료로 상담해 보세요.")
    return reply, []
