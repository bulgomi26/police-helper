"""데모 시나리오 점검 스크립트. 실행: python -m tests.run_scenarios

1부: LLM 없이 도구만 실행해 데모 3개가 기대한 결과를 내는지 확인
2부: 가짜 LLM으로 에이전트 루프(도구 호출 → 결과 전달 → 최종 답)가 도는지 확인
3부: data 파일의 검증 안 된 항목(TODO, verified=false) 목록 출력 — 제출 전 0개가 목표
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):  # 윈도우 콘솔(cp949)에서 이모지 출력 오류 방지
    sys.stdout.reconfigure(encoding="utf-8")

from agent import Agent  # noqa: E402
from tools import run_tool  # noqa: E402
from tools.data_loader import load  # noqa: E402

failures = []


def check(name, cond, detail=""):
    print(("  ✅ " if cond else "  ❌ ") + name + (f"  ({detail})" if detail and not cond else ""))
    if not cond:
        failures.append(name)


# ---------- 1부: 도구 ----------
print("\n[1부] 데모 시나리오 도구 점검")

print("시나리오 1: 사칭 문자")
s1 = ("중수청 수사관입니다. 고객님 명의 대포통장이 범죄에 연루되어 출석이 필요합니다. "
      "첨부 출석요구서 확인 바람 http://sci-notice.xyz/doc 비밀 수사이니 가족에게 알리지 마세요. 010-1234-5678")
r = run_tool("analyze_message", {"text": s1})
check("사칭 의심 높음 판정", r["verdict"] == "high", r["verdict"])
ids = {s["id"] for s in r["signals"]}
check("링크·파일 신호", "file_or_link_document" in ids, ids)
check("비밀 유지 압박 신호", "secrecy_pressure" in ids, ids)
check("대포통장 신호", "bank_account_crime" in ids, ids)
check("중수청 인식", "중대범죄수사청" in r["extracted"]["orgs"], r["extracted"])
check("전화번호 추출", "010-1234-5678" in r["extracted"]["phones"], r["extracted"]["phones"])
c = run_tool("check_official_contact", {"org_name": "중수청", "phone": "010-1234-5678"})
check("중수청 번호 대조 → 확인 필요", c["status"] == "verify_needed", c["status"])
np_ = run_tool("check_official_contact", {"org_name": "○○경찰서 수사과", "phone": ""})
check("번호를 안 줬으면 번호 대조 안 함", np_["status"] == "no_phone" and "대표번호가 아닙니다" not in np_["message"], np_)
f = run_tool("check_official_contact", {"org_name": "사이버수사국"})
check("존재하지 않는 조직 탐지", f["status"] == "fake_org", f["status"])

print("시나리오 2: 참고인 출석요구 (중고거래)")
s2 = "○○경찰서 수사과라며 전화가 왔어요. 중고거래 사기 사건 관련해서 참고인으로 다음 주 화요일에 출석해 달래요."
r = run_tool("analyze_message", {"text": s2})
check("사칭 신호 낮음", r["verdict"] == "low", (r["verdict"], r["signals"]))
check("참고인 신분 추출", "참고인" in r["extracted"]["roles"], r["extracted"]["roles"])
law = run_tool("search_law", {"query": "출석 연기", "tags": ["연기", "참고인"]})
check("연기 관련 조문 검색", any(a["id"] == "rule_19" for a in law["results"]), [a["id"] for a in law["results"]])
card = run_tool("get_strategy_card", {"card_id": "reference_alone"})
check("참고인 카드", card.get("id") == "reference_alone")
risk = run_tool("assess_risk", {"signal_ids": []})
check("상담 필요도 🟢", risk["level"] == "green", risk["level"])
doc = run_tool("draft_document", {"doc_type": "postpone_request", "fields": {"station": "○○경찰서 수사과", "reason": "시험"}})
check("연기 요청 말하기 문장 생성", "시험" in doc["text"] and "○○○" in doc["text"] and "label" in doc)
check("연기 요청 전화·문자 두 버전", len(doc.get("versions", [])) == 2 and "문자" in doc["versions"][1]["channel"])
prep = run_tool("draft_document", {"doc_type": "prep_list", "fields": {"role": "참고인"}})
check("참고인 준비 목록", "신분증" in prep["text"] and "신분이 바뀐" in prep["text"])
ask = run_tool("draft_document", {"doc_type": "ask_case_info", "fields": {"evidence": "CCTV 영상"}})
check("사건 내용 확인 문장 생성", "CCTV 영상" in ask["text"] and "출석요구서" in ask["text"])

print("시나리오 3: 성범죄 피의자 (동탄형)")
risk = run_tool("assess_risk", {"signal_ids": ["suspect_status", "testimony_only", "unverified_evidence",
                                               "pressure_remarks", "unknown_charge", "serious_charge"],
                                "sex_crime_suspect": True})
check("상담 필요도 🔴", risk["level"] == "red", risk["level"])
check("신호 6개 집계", risk["count"] == 6, risk["count"])
risk2 = run_tool("assess_risk", {"signal_ids": ["suspect_status"], "sex_crime_suspect": True})
check("성범죄 피의자는 신호 1개여도 🔴", risk2["level"] == "red", risk2["level"])
for cid in [c["id"] for c in load("strategy_cards")["cards"]]:
    cd = run_tool("get_strategy_card", {"card_id": cid})
    if cd.get("format") == "guide":  # 안내형 카드: 질문에 바로 답하는 항목들
        check(f"{cid} 카드 (안내형: 첫 문장 + 항목)", cd.get("id") == cid and cd.get("lead") and cd.get("sections") and all(
            sec.get("title") and sec.get("points") for sec in cd["sections"]))
    else:
        check(f"{cid} 카드 (표 형식 칸 5개)", cd.get("id") == cid and all(
            all(o.get(k) for k in ["name", "when", "good", "caution", "say"]) for o in cd["options"]))
vs = run_tool("check_official_contact", {"org_name": "○○경찰서 수사과"})
check("경찰 확인 단계 4개 (182)", len(vs["verify_steps"]) == 4 and "182" in vs["verify_steps"][2])
vs2 = run_tool("check_official_contact", {"org_name": "중수청"})
check("중수청 확인 단계 (110)", any("110" in x for x in vs2["verify_steps"]))

print("법령 데이터 (11/19 개정법 반영)")
p = run_tool("analyze_message", {"text": "서울중앙지검 검사입니다. 내일까지 검사실로 출석하세요."})
check("검사 직접 출석요구 신호", any(s["id"] == "prosecutor_summons" for s in p["signals"]), p["signals"])
rec = run_tool("search_law", {"query": "녹음", "tags": ["녹음"]})
up = [a for a in rec["results"] if a["id"] == "cpa_244_6"]
check("녹음 요청권 조문은 '시행 예정'", bool(up) and up[0]["status"] == "upcoming", up)
check("검찰청 → 공소청 매칭", run_tool("check_official_contact", {"org_name": "서울중앙지검"}).get("agency") == "공소청")

print("권하는 순서")
pl = run_tool("get_action_plan", {"role": "피의자", "risk_level": "red"})
check("피의자: 날짜 미루기 → 사건 확인 → 변호사 → 준비", [x["block"] for x in pl["steps"]] == ["postpone", "case_check", "lawyer", "prep"], pl)
pl2 = run_tool("get_action_plan", {"role": "참고인", "risk_level": "green"})
check("참고인 🟢: 사건 확인이 먼저", pl2["steps"][0]["block"] == "case_check", pl2)
pl3 = run_tool("get_action_plan", {"role": "모름"})
check("신분 모름 → 피의자 기준 순서", pl3["plan_id"] == "suspect_or_risky" and pl3["role_unknown"], pl3)
check("사건 확인 문장에 사건번호 요청", "사건번호" in run_tool("draft_document", {"doc_type": "ask_case_info"})["text"])

print("준비물·순서와 기본 안내 모드")
pl4 = run_tool("get_action_plan", {"role": "피의자"})
law_step = next(x for x in pl4["steps"] if x["block"] == "lawyer")
check("변호사 블록: 준비물·순서·132 문장", law_step["prepare"] and "132" in law_step["how"][0] and law_step["doc_type"] == "consult_request")
cr = run_tool("draft_document", {"doc_type": "consult_request", "fields": {"role": "피의자"}})
check("132 상담 신청 문장", "피의자 신분으로" in cr["text"])
from fallback import basic_answer, basic_followup
fb, fev = basic_answer(s2)
check("기본 안내: 지금 할 일·확인 단계·①~④", fb.startswith("**지금 할 일**") and "182" in fb and "### ④" in fb and "**준비물**" in fb)
fb1, _ = basic_answer(s1)
check("기본 안내: 사칭이면 경고만", "사칭 가능성이 높아요" in fb1 and "### ①" not in fb1)
fu, fuev = basic_followup("조사실에서 녹음해도 돼요?")
check("기본 안내 후속 질문: 녹음 카드", fuev and fuev[0]["result"]["id"] == "recording")

print("이어서 물어보기 (질문 버튼)")
from tools.followups import catalog
sv = run_tool("get_strategy_card", {"card_id": "silence"})
check("진술거부 카드: 관련 내용 한 번에 (쪼개지 않음)", len(sv["sections"]) == 5)
cards_all = load("strategy_cards")["cards"]
check("버튼 = 카드 하나씩 (한 주제를 쪼갠 질문 없음)", sorted(x["id"] for x in catalog()) == sorted(c["id"] for c in cards_all))
check("관련 카드는 모두 실제로 있는 카드", all(r in {c["id"] for c in cards_all} for c in cards_all for r in c.get("related", [])))
check("카드 근거 조문이 모두 데이터에 있음",
      all(b in {a["id"] for a in load("laws")["articles"]} for c in cards_all for b in c.get("basis", [])))
sq = run_tool("suggest_questions", {"ids": ["recording", "없는_id", "recording", "silence"]})
check("질문 고르기: 없는 id·중복 버림", [x["id"] for x in sq["questions"]] == ["recording", "silence"])
check("질문 고르기: 빈 목록이면 버튼 없음", run_tool("suggest_questions", {"ids": []})["questions"] == [])
fb_sus = basic_answer("경찰서에서 피의자로 출석하라고 전화가 왔어요")[1]
check("첫 답변: 카드 대신 질문 버튼 (피의자 → 진술거부·불출석·조서)",
      not any(e["tool"] == "get_strategy_card" for e in fb_sus)
      and [x["id"] for x in fb_sus[-1]["result"]["questions"]] == ["silence", "no_show", "read_record"])
fb_phone = basic_answer("카톡 대화 때문에 피의자로 경찰서에 출석하라는 전화를 받았어요")[1]
check("첫 답변: 휴대폰 자료가 걸린 피의자 → 휴대폰 제출 카드", [x["id"] for x in fb_phone[-1]["result"]["questions"]] == ["silence", "phone_submit", "no_show"])
fb_sex = basic_answer("헬스장 화장실 관련 신고가 들어왔다며 피의자로 출석하라고 경찰서에서 전화가 왔어요")[1]
check("첫 답변: 성범죄 피의자 → 휴대폰 제출 카드", "phone_submit" in [x["id"] for x in fb_sex[-1]["result"]["questions"]])
check("첫 답변: 참고인 → 혼자 가기·출석 의무·녹음",
      [x["id"] for x in fev[-1]["result"]["questions"]] == ["reference_alone", "reference_no_show", "recording"])
for q, cid in [("휴대폰 꼭 내야 돼요?", "phone_submit"), ("조서에 서명해도 돼요?", "read_record"),
               ("조사가 밤늦게까지 길어지면요?", "interview_time"), ("출석 안 하면 어떻게 돼요?", "no_show")]:
    check(f"기본 안내 자유 질문 → {cid}", basic_followup(q)[1][0]["result"]["id"] == cid)
check("사칭 의심이면 질문 버튼 없음", not any(e["tool"] == "suggest_questions" for e in basic_answer(s1)[1]))
for item in catalog():  # 버튼을 누르면 AI 없이도 같은 카드가 나오고, 관련 카드만 다음 버튼으로
    _, ev = basic_followup(item["q"])
    nxt = [x["id"] for x in ev[1]["result"]["questions"]]
    check(f"버튼 '{item['q']}' → {item['card']} 카드, 다음 버튼 {nxt}",
          ev[0]["result"]["id"] == item["card"] and item["card"] not in nxt and set(nxt) <= set(item["related"]))

print("잘못된 요청 처리")
check("없는 도구 → 오류 dict", "error" in run_tool("nope", {}))
check("잘못된 JSON → 오류 dict", "error" in run_tool("search_law", "{bad json"))
check("없는 카드 → 오류 dict", "error" in run_tool("get_strategy_card", {"card_id": "x"}))


# ---------- 2부: 가짜 LLM으로 에이전트 루프 ----------
print("\n[2부] 에이전트 루프 (가짜 LLM)")


class FakeClient:
    """첫 호출: analyze_message 도구 호출 / 둘째 호출: 최종 답변"""

    def __init__(self):
        self.calls = []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            tc = NS(id="call_1", function=NS(name="analyze_message", arguments=json.dumps({"text": s1}, ensure_ascii=False)))
            msg = NS(content=None, tool_calls=[tc])
        else:
            msg = NS(content="사칭 가능성이 높아요. 링크를 열지 마세요.", tool_calls=None)
        return NS(choices=[NS(message=msg)])


fake = FakeClient()
reply, events, history = Agent(fake, "fake-model").run([{"role": "user", "content": s1}])
check("LLM 2번 호출", len(fake.calls) == 2, len(fake.calls))
check("도구 이벤트 1개", len(events) == 1 and events[0]["tool"] == "analyze_message")
check("도구 결과가 tool 메시지로 전달", any(m["role"] == "tool" for m in fake.calls[1]["messages"]))
check("시스템 프롬프트 포함", fake.calls[0]["messages"][0]["role"] == "system")
check("최종 답변 반환", "사칭" in reply)
check("history에 assistant(tool_calls)·tool·assistant 순서", [m["role"] for m in history] == ["user", "assistant", "tool", "assistant"])


# ---------- 보안: 입력 검사·답변 검사기 ----------
print("\n[보안] 개인정보 가리기·지시문 찾기·답변 검사기")
from guard import check_output, prepare_input  # noqa: E402
from tests.attack_cases import (BAD_REPLIES, DIRECT_OVERRIDE, FALLBACK_CASES, NORMAL,  # noqa: E402
                                PII_CASES, PROMPT_LEAK, SCAM_WITH_DIRECTIVE, URL_CASES)

print("개인정보 가리기")
for text, gone, kept in PII_CASES:
    shown = prepare_input(text)["shown"]
    check(f"가림: {text[:20]}", (not gone or gone not in shown) and kept in shown, shown)
print("사칭 문자 속 AI 지시문 → 사칭 의심 높음")
for t in SCAM_WITH_DIRECTIVE:
    a = run_tool("analyze_message", {"text": t})
    check(f"{t[:22]}…", "ai_directive" in prepare_input(t)["flags"] and a["verdict"] == "high", a["verdict"])
print("직접 지시 변경 → 경고 붙여 전달 또는 고정 답변")
for t in DIRECT_OVERRIDE:
    r = prepare_input(t)
    check(f"{t[:22]}…", "override" in r["flags"] and "따르지 말고" in r["sent"], list(r["flags"]))
print("프롬프트 유출 시도 → AI 호출 없이 고정 답변")
for t in PROMPT_LEAK:
    r = prepare_input(t)
    check(f"{t[:22]}…", r["static"] is not None, list(r["flags"]))
print("정상 질문은 걸리지 않음 (오탐)")
for t in NORMAL:
    r = prepare_input(t)
    a = run_tool("analyze_message", {"text": t})
    check(f"{t[:22]}…", not r["flags"] and not r["static"] and a["verdict"] != "high", r["flags"])
print("답변 검사기")
for bad in BAD_REPLIES:
    check(f"차단: {bad[:22]}…", bool(check_output(bad)))
for name, txt in [("데모2 기본 안내", basic_answer(s2)[0]), ("사칭 기본 안내", basic_answer(s1)[0]),
                  ("피의자 기본 안내", basic_answer("경찰서에서 피의자로 출석하라고 전화가 왔어요")[0])]:
    probs = check_output(txt)
    check(f"통과: {name}", not probs, probs)
check("사용자 글은 <사용자 입력>으로 감싸 전달", prepare_input(s2)["sent"].startswith("<사용자 입력>"))

print("공식 주소 링크 오탐 (외부 검토 반영)")
for t, want in URL_CASES:
    v = run_tool("analyze_message", {"text": t})["verdict"]
    check(f"{t[:24]}… → {want}", (v == "high") == (want == "high"), v)
print("기본 안내 모드 분기 (외부 검토 반영)")
for t, must, must_not in FALLBACK_CASES:
    out = basic_answer(prepare_input(t)["shown"])[0]
    check(f"{t[:24]}…", must in out and must_not not in out, out[:80])
    check(f"  └ 답변 검사 통과", not check_output(out), check_output(out))
print("화면에 나가는 데이터 문구 전체 검사 (카드·계획·문장 템플릿·기관 안내)")


def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)


from tools.draft_document import TEMPLATES  # noqa: E402
for src in ["strategy_cards", "action_plans", "agencies", "scam_rules", "risk_signals"]:
    bad = [(t[:40], check_output(t)) for t in _strings(load(src)) if check_output(t)]
    check(f"data/{src}.json 문구", not bad, bad[:2])
bad = [(k, check_output(str(v))) for k, v in TEMPLATES.items() if check_output(str(v))]
check("말할 문장 템플릿", not bad, bad[:2])


# ---------- 3부: 데이터 검증 현황 ----------
print("\n[3부] 제출 전 채워야 할 데이터")
todo = [f"laws: {a['law']} {a['article']}" for a in load("laws")["articles"] if not a["verified"]]
todo += [f"agencies: {a['name']}" for a in load("agencies")["agencies"] if not a["verified"]]
for cdef in load("strategy_cards")["cards"]:
    if cdef["common_ground"].startswith("TODO") or any(v["summary"].startswith("TODO") for v in cdef["expert_views"]):
        todo.append(f"strategy_cards: {cdef['id']} (영상 요약)")
    elif cdef.get("evidence_pending"):
        todo.append(f"strategy_cards: {cdef['id']} (조문 근거만 있음, 변호사 영상 근거 연결 전)")
for t in todo:
    print("  ⏳ " + t)
print(f"  → 남은 항목 {len(todo)}개")

print(f"\n결과: 실패 {len(failures)}개" + (f" → {failures}" if failures else " (모두 통과)"))
sys.exit(1 if failures else 0)
