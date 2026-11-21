"""Streamlit 화면. 실행: streamlit run app.py

대화 내용은 브라우저 세션(st.session_state)에만 있고 서버에 저장하지 않는다.
"""
import re

import streamlit as st

from datetime import datetime

from agent import Agent, make_client
import time

from config import MAX_AGENT_STEPS, MAX_OUTPUT_TOKENS, MAX_TURNS_PER_SESSION, TURN_TIME_LIMIT, llm_chain
from compose import first_answer
from fallback import basic_answer, basic_followup
from guard import MAX_INPUT_CHARS, check_output, masked_notice, prepare_input

st.set_page_config(page_title="수사 초기 대응 도우미", page_icon="🛡️", layout="wide")

# '근거 보기' 버튼 모양 (답변 본문의 <details>)
st.markdown(
    """
<style>
details.evidence { margin: 4px 0 18px 0; }
details.evidence > summary {
  display: inline-flex; align-items: center; gap: 6px;
  list-style: none; cursor: pointer; user-select: none;
  padding: 6px 16px; border-radius: 999px;
  background: #EEF4FF; color: #1E4FD8; border: 1px solid #B9CCFF;
  font-size: 0.9rem; font-weight: 600;
  box-shadow: 0 1px 2px rgba(30, 79, 216, 0.12);
  transition: background 0.15s ease;
}
details.evidence > summary::-webkit-details-marker { display: none; }
details.evidence > summary::marker { content: ""; }
details.evidence > summary:hover { background: #DCE7FF; }
details.evidence[open] > summary { background: #1E4FD8; color: #FFFFFF; border-color: #1E4FD8; }
details.evidence .when-open { display: none; }
details.evidence[open] .when-open { display: inline; }
details.evidence[open] .when-closed { display: none; }
details.evidence > div {
  margin-top: 8px; padding: 10px 14px;
  background: #F7F9FF; border-left: 3px solid #1E4FD8; border-radius: 6px;
  font-size: 0.92rem; line-height: 1.6;
}
table.strategy {
  width: 100%; table-layout: fixed; border-collapse: separate; border-spacing: 0;
  border: 1px solid #E2E8F0; border-radius: 10px; overflow: hidden;
  font-size: 0.95rem; line-height: 1.65; margin: 6px 0 12px 0;
}
table.strategy th {
  background: #F1F5F9; color: #334155; font-weight: 700; text-align: left;
  padding: 12px 14px; border-bottom: 1px solid #E2E8F0;
}
table.strategy td {
  padding: 14px; vertical-align: top; color: #1E293B;
  border-bottom: 1px solid #EEF2F6; word-break: keep-all;
}
table.strategy tr:last-child td { border-bottom: none; }
table.strategy tbody tr:nth-child(even) td { background: #FAFBFC; }
table.strategy td.opt .name { font-weight: 700; font-size: 1.02rem; color: #0F172A; margin-bottom: 6px; }
table.strategy td.opt .when { font-size: 0.85rem; color: #64748B; }
table.strategy td.say { background: #FFF8E6 !important; border-left: 3px solid #F5B301; font-weight: 500; }
/* 휴대폰: 표를 선택지별 카드로 */
@media (max-width: 700px) {
  table.strategy, table.strategy tbody, table.strategy tr, table.strategy td { display: block; width: 100%; }
  table.strategy colgroup, table.strategy thead { display: none; }
  table.strategy { border: none; }
  table.strategy tr { border: 1px solid #E2E8F0; border-radius: 10px; margin-bottom: 12px; overflow: hidden; }
  table.strategy td { border-bottom: 1px solid #EEF2F6; padding: 10px 12px; }
  table.strategy td[data-label]::before {
    content: attr(data-label); display: block; font-size: 0.8rem; font-weight: 700; color: #64748B; margin-bottom: 4px;
  }
  table.strategy tbody tr:nth-child(even) td { background: transparent; }
}
.privacy-note {
  font-size: 0.88rem; color: #475569; background: #F8FAFC; border: 1px solid #E2E8F0;
  border-radius: 8px; padding: 8px 12px; margin: 4px 0 12px 0;
}
</style>
""",
    unsafe_allow_html=True,
)

DEMOS = {
    "① 사칭 의심 문자": "중수청 수사관입니다. 고객님 명의 대포통장이 범죄에 연루되어 출석이 필요합니다. "
    "첨부 출석요구서 확인 바람 http://sci-notice.xyz/doc 비밀 수사이니 가족에게 알리지 마세요. 010-1234-5678",
    "② 참고인 (중고거래)": "○○경찰서 수사과라며 전화가 왔어요. 중고거래 사기 사건 관련해서 참고인으로 다음 주 화요일에 "
    "출석해 달래요. 그날은 시험이 있어서 못 갈 것 같은데 어떻게 하죠?",
    "③ 피의자 (성범죄)": "헬스장 화장실 관련 신고가 들어왔다며 피의자로 출석하라고 경찰서에서 전화가 왔어요. "
    "저는 그런 적이 없는데 수사관이 'CCTV 영상이 있다', '떳떳하면 가만히 있으면 된다'고 했어요. 무슨 혐의인지 자세히는 몰라요.",
}


START_GUIDES = {
    "📞 전화 받음": "통화에서 들은 내용을 아래처럼 적어 주세요. 기억나는 것만 써도 돼요.\n\n"
    "- 어디서 연락했는지 (예: ○○경찰서 수사과)\n"
    "- 내 신분 (피의자 / 참고인 / 못 들었음)\n"
    "- 무슨 일 때문인지 (예: 중고거래, 댓글)\n"
    "- 출석하라는 날짜\n"
    "- 수사관이 한 말 중 마음에 걸리는 말\n\n"
    "이름·주민번호·전화번호는 적지 마세요.",
    "💬 문자 받음": "받은 문자를 그대로 붙여 넣어 주세요.\n\n"
    "- 문자 속 링크나 파일은 누르지 마세요.\n"
    "- 내 이름이나 주민번호가 들어 있으면 지우고 붙여 넣으세요.",
    "📄 출석요구서 받음": "출석요구서에서 아래 내용만 옮겨 적어 주세요.\n\n"
    "- 보낸 기관 (예: ○○경찰서 ○○과)\n"
    "- 내 신분 (피의자 / 참고인)\n"
    "- 사건 내용이나 죄명\n"
    "- 출석 일시\n\n"
    "이름·주민번호·주소·사건번호는 적지 마세요.",
}

# ---------- 상태 ----------
def init_state():
    st.session_state.setdefault("history", [])  # LLM에 보내는 메시지 (tool 포함)
    st.session_state.setdefault("display", [])  # 화면용 [{role, content, events}]
    st.session_state.setdefault("turns", 0)


def reset():
    for k in ["history", "display", "turns"]:
        st.session_state.pop(k, None)


init_state()


def safe_md(text):
    """모델 답변 표시용.
    - HTML은 글자로 바꾼다 (모델 출력에 섞인 태그 차단)
    - 한글 조사가 붙어 깨지는 **굵게**는 <strong>으로 바꾼다
    - '근거:'로 시작하는 줄은 접었다 펼 수 있게 만든다
    """
    text = (text or "").replace("&", "&amp;").replace("<", "&lt;")  # 태그만 막고 인용(>)은 살림
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    out = []
    for line in text.splitlines():
        m = re.match(r"^\s*(?:[-*]\s*)?(?:<strong>)?근거(?:</strong>)?\s*[:：]\s*(?:</strong>)?\s*(.+)$", line)
        if m:
            out += ["", '<details class="evidence"><summary>📖 '
                    '<span class="when-closed">근거 보기 ▾</span><span class="when-open">근거 접기 ▴</span>'
                    f"</summary><div>{m.group(1)}</div></details>", ""]
        else:
            out.append(line)
    return "\n".join(out)


def hide_todo(text):
    return "" if not text or text.strip().startswith("TODO") else text


# ---------- 카드 렌더링 ----------
def law_label(a):
    base = a["label"] if "label" in a else f"{a['law']} {a['article']} ({a['title']})"
    if a.get("status") == "upcoming":
        base += " · 🕒 시행 예정"
    return base + ("" if a.get("verified") else " · 검증 전")


def render_event(ev):
    name, r = ev["tool"], ev["result"]
    if "error" in r:
        return
    if name == "analyze_message":
        if r["verdict"] == "low":
            return  # 사칭 신호가 없으면 따로 표시하지 않음 (확인 방법은 답변의 할 일에 들어감)
        box = {"high": st.error, "check": st.warning}[r["verdict"]]
        lines = [f"**사칭 점검: {r['verdict_label']}**"]
        lines += [f"- {s['label']}: {s['why']}" for s in r["signals"]]
        lines.append(f"\n{r['advice']}")
        box("\n".join(lines))
    elif name == "check_official_contact":
        if r["status"] == "fake_org":
            st.error(f"**기관 대조**: {r['message']}")
            return
        if not ev.get("show_contact"):
            return  # 사칭 의심이 아니면 화면에 다시 보여 주지 않음
        msg = f"**확인 방법**: {r['message']}"
        if r["status"] in ("verify_needed", "matched") and hide_todo(r.get("how_to_verify")):
            msg += f"  \n{r['how_to_verify']}"
        if r.get("extra_contacts"):
            msg += "  \n" + ", ".join(f"{k} {v}" for k, v in r["extra_contacts"].items())
        st.info(msg)
    elif name == "search_law":
        with st.expander(f"📖 관련 조문 {r['found']}개"):
            for a in r["results"]:
                st.markdown(f"**{law_label(a)}**  \n{a['summary']}  \n[국가법령정보센터에서 원문 보기]({a['source_url']})")
    elif name == "assess_risk":
        box = {"green": st.success, "yellow": st.warning, "red": st.error}[r["level"]]
        head = f"### {r['emoji']} {r['label']}  ({r['count']}/{r['total_signals']}개 신호)\n{r['recommendation']}"
        if r["sex_crime_override"]:
            head += "\n\n※ 성범죄 피의자 출석요구는 신호 개수와 관계없이 🔴로 안내합니다."
        box(head)
        with st.expander("왜 이렇게 안내하나요? (근거)"):
            if r["matched"]:
                for s_ in r["matched"]:
                    basis = ", ".join(law_label(b) for b in s_["basis"])
                    st.markdown(f"- **{s_['label']}**: {s_['meaning']}" + (f"  \n  근거: {basis}" if basis else ""))
            else:
                st.markdown("확인된 위험 신호가 없습니다.")
            st.caption(r["notice"])
    elif name == "get_strategy_card":
        with st.container(border=True):
            st.markdown(f"#### 🧭 {r['title']}")
            def esc(t):
                return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br>")
            rows = []
            for opt in r["options"]:
                rows.append(
                    "<tr>"
                    f"<td class='opt'><div class='name'>{esc(opt['name'])}</div>"
                    f"<div class='when'>이럴 때: {esc(opt.get('when'))}</div></td>"
                    f"<td data-label='✅ 이렇게 돼요'>{esc(opt.get('good'))}</td>"
                    f"<td data-label='⚠️ 이건 조심하세요'>{esc(opt.get('caution'))}</td>"
                    f"<td class='say' data-label='💬 실제로 이렇게 말해요'>{esc(opt.get('say'))}</td>"
                    "</tr>"
                )
            st.markdown(
                "<table class='strategy'>"
                "<colgroup><col style='width:24%'><col style='width:25%'><col style='width:25%'><col style='width:26%'></colgroup>"
                "<thead><tr><th>선택</th><th>✅ 이렇게 돼요</th><th>⚠️ 이건 조심하세요</th><th>💬 실제로 이렇게 말해요</th></tr></thead>"
                f"<tbody>{''.join(rows)}</tbody></table>",
                unsafe_allow_html=True,
            )
            if not r["common_ground"].startswith("TODO"):
                st.markdown(f"**실무자들이 공통으로 말하는 것**: {r['common_ground']}")
                st.markdown(f"**의견이 갈리는 지점**: {r['disagreement']}")
            views = [v for v in r["expert_views"] if not v["summary"].startswith("TODO")]
            if views:
                with st.expander("실무자 견해 보기"):
                    for v in views:
                        link = f" [영상]({v['url']})" if v["url"] else ""
                        st.markdown(f"- **{v['source']}**{link}: {v['summary']}" + (f"  \n  _{v['bias_note']}_" if v["bias_note"] else ""))
            with st.expander("확인할 점과 근거"):
                for c in r.get("check_points", []):
                    st.markdown(f"- {c}")
                if r["basis_articles"]:
                    st.caption("근거: " + ", ".join(law_label(b) for b in r["basis_articles"]))
            st.caption(r["notice"])
    elif name == "draft_document":
        if ev.get("inlined"):
            return  # 답변 본문에 이미 들어 있으면 중복 표시하지 않음
        st.markdown(f"**{r['label']}**")
        for v in r.get("versions") or [{"channel": "", "text": r["text"]}]:
            if v["channel"]:
                st.markdown(v["channel"])
            st.markdown("\n".join("> " + line for line in v["text"].splitlines()))
            if v.get("tip"):
                st.caption(v["tip"])


AI_LABEL = "🤖 AI가 생성한 답변입니다. 법률 자문이 아니며, 근거 조문과 연락처는 함께 표시된 카드를 확인하세요."


TOP_TOOLS = {"analyze_message", "check_official_contact"}


def prepare_events(events, reply):
    """화면 표시용 플래그를 붙인다: 사칭 의심일 때만 기관 확인 카드, 본문에 들어간 문장은 중복 숨김."""
    suspicious = any(e["tool"] == "analyze_message" and e["result"].get("verdict") in ("high", "check")
                     for e in events)
    compact_reply = (reply or "").replace(" ", "")
    for e in events:
        if e["tool"] == "check_official_contact":
            e["show_contact"] = suspicious
        if e["tool"] == "draft_document" and "text" in e["result"]:
            first_line = e["result"]["text"].splitlines()[0].replace(" ", "")[:25]
            e["inlined"] = bool(first_line) and first_line in compact_reply
    return events


def render_assistant(events, reply, static=False, fallback=False):
    if static:
        st.markdown(reply)
        return
    if fallback == "blocked":
        st.warning("AI 답변이 안전 검사를 통과하지 못해, 미리 검증된 기본 안내로 보여 드려요.")
    elif fallback:
        st.warning("AI 연결이 원활하지 않아 기본 안내로 보여 드려요. 아래 내용은 미리 검증된 안내예요.")
    for ev in events:
        if ev["tool"] in TOP_TOOLS:
            render_event(ev)
    if reply:
        st.markdown(safe_md(reply), unsafe_allow_html=True)
    rest = [ev for ev in events if ev["tool"] not in TOP_TOOLS and "error" not in ev["result"]]
    shown = [ev for ev in rest if not (ev["tool"] == "draft_document" and ev.get("inlined"))]
    if shown:
        st.markdown("---")
        st.caption("근거와 자세한 내용")
        for ev in shown:
            render_event(ev)
    st.caption("🔧 AI 없이 미리 정해 둔 규칙으로 만든 기본 안내입니다. 법률 자문이 아닙니다." if fallback else AI_LABEL)


def render_message(item):
    with st.chat_message(item["role"]):
        if item["role"] == "assistant":
            render_assistant(item.get("events", []), item["content"],
                             static=item.get("static", False), fallback=item.get("fallback", False))
        else:
            st.markdown(item["content"])
            if item.get("notice"):
                st.caption(item["notice"])


# ---------- 사이드바 ----------
with st.sidebar:
    st.markdown("### 🛡️ 수사 초기 대응 도우미")
    st.caption(
        "권리와 절차를 안내하는 서비스이며 법률 자문이 아닙니다.\n\n"
        "입력한 내용은 답변을 만들기 위해 외부 AI 서비스로 전송됩니다. "
        "이 앱은 대화를 저장하지 않고, 창을 닫으면 사라집니다.\n\n"
        "실명·주민등록번호·전화번호·사건번호는 입력하지 마세요."
    )
    st.markdown("**데모 예시**")
    demo_clicked = None
    for label, text in DEMOS.items():
        if st.button(label, use_container_width=True):
            demo_clicked = text
    if st.button("대화 새로 시작", use_container_width=True):
        reset()
        st.rerun()
    st.caption(f"남은 질문 수: {MAX_TURNS_PER_SESSION - st.session_state.turns}")
    if st.session_state.get("tokens"):
        st.caption(f"이번 세션 사용 토큰: {st.session_state.tokens:,}")


# ---------- 본문 ----------
st.title("경찰 연락, 혼자 대응하지 마세요")
st.caption("수사기관과 통화를 마친 뒤, 받은 문자나 들은 내용을 넣어 주세요. 진짜인지 확인하는 방법부터 할 일 순서까지 정리해 드려요.")
st.markdown(
    "<div class='privacy-note'>🔒 입력한 내용은 답변을 만들기 위해 외부 AI 서비스로 전송돼요. "
    "이 앱은 대화를 저장하지 않지만, <b>이름·주민번호·전화번호·주소·사건번호는 넣지 마세요.</b> "
    "번호·주소·'○○님' 형태의 이름은 자동으로 가리지만, 모든 개인정보를 잡지는 못해요.</div>",
    unsafe_allow_html=True,
)

if not st.session_state.display:
    st.markdown("**어떤 연락을 받으셨나요?**")
    cols = st.columns(len(START_GUIDES))
    for col, (label, guide) in zip(cols, START_GUIDES.items()):
        if col.button(label, use_container_width=True):
            st.session_state.display.append({"role": "assistant", "content": guide, "static": True})
            st.rerun()
    st.markdown("**처음이라면 예시로 먼저 보세요** (가상의 상황이에요)")
    dcols = st.columns(len(DEMOS))
    for col, (label, text) in zip(dcols, DEMOS.items()):
        if col.button(label, use_container_width=True, key=f"main_{label}"):
            demo_clicked = text

for item in st.session_state.display:
    render_message(item)


def last_answer():
    for item in reversed(st.session_state.display):
        if item["role"] == "assistant" and not item.get("static"):
            return item["content"]
    return None


if last_answer():
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    note = (f"[수사 초기 대응 도우미] {stamp} 기준 안내\n"
            "※ 법률 자문이 아닌 절차 안내입니다. 개별 판단은 변호사·대한법률구조공단(132)에 확인하세요.\n\n")
    st.download_button("📄 내 상황과 할 일 저장하기 (내 휴대폰에만 저장돼요)",
                       data=note + last_answer(), file_name=f"할일_{stamp[:10]}.txt", mime="text/plain")

user_text = st.chat_input("예: 경찰서에서 출석하라는 전화를 받았어요", max_chars=MAX_INPUT_CHARS) or demo_clicked

if user_text:
    if st.session_state.turns >= MAX_TURNS_PER_SESSION:
        st.warning("이번 세션의 질문 수를 다 썼어요. 사이드바에서 '대화 새로 시작'을 눌러 주세요.")
        st.stop()

    st.session_state.turns += 1
    # 입력 검사: 개인정보 가리기 → 지시문 찾기 → '데이터'로 감싸기 (외부 AI에는 가린 글만 간다)
    prepared = prepare_input(user_text)
    if prepared["flags"]:
        print(f"[입력 검사] 지시문 의심: {prepared['flags']}")
    user_item = {"role": "user", "content": prepared["shown"], "notice": masked_notice(prepared["masked"])}
    st.session_state.display.append(user_item)
    render_message(user_item)

    if prepared["static"]:  # 상황 설명 없이 지시 변경·내부 정보 요청만 있으면 AI를 부르지 않는다
        st.session_state.display.append({"role": "assistant", "content": prepared["static"], "static": True})
        st.rerun()

    st.session_state.history.append({"role": "user", "content": prepared["sent"]})
    user_text = prepared["shown"]

    chain = llm_chain()
    fallback_used = False
    with st.chat_message("assistant"):
        with st.spinner("확인하고 있어요..."):
            try:
                reply = None
                start, last_error = time.time(), None
                for settings in chain:  # 기본 제공자 → (한도 초과 등으로 실패하면) 예비 제공자
                    if not settings["api_key"]:
                        last_error = RuntimeError(f"{settings['provider']} API 키가 설정되지 않았습니다.")
                        continue
                    remaining = TURN_TIME_LIMIT - (time.time() - start)
                    if remaining < 15:
                        break
                    try:
                        agent = Agent(make_client(settings), settings["model"], max_steps=MAX_AGENT_STEPS,
                                      time_limit=remaining, max_tokens=MAX_OUTPUT_TOKENS,
                                      extra_body=settings.get("extra_body"))
                        if st.session_state.turns == 1:
                            # 첫 질문: AI가 상황을 정리 → 검증된 데이터로 안내 조립
                            reply, events, slots = first_answer(agent, st.session_state.history, user_text)
                            print(f"[AI 상황 정리] {slots}")
                            history = st.session_state.history + [{"role": "assistant", "content": reply}]
                        else:
                            reply, events, history = agent.run(st.session_state.history)
                        print(f"[모델] {settings['provider']} / {settings['model']}")
                        break
                    except Exception as e:
                        last_error = e
                        print(f"[모델 실패] {settings['provider']}: {type(e).__name__}: {str(e)[:200]}")
                if reply is None:
                    raise last_error or RuntimeError("사용할 수 있는 AI 제공자가 없습니다.")
                st.session_state.setdefault("tokens", 0)
                st.session_state.tokens += agent.tokens
                print(f"[토큰] 이번 답변 {agent.tokens:,} (호출 {agent.calls}번) / 세션 누적 {st.session_state.tokens:,}")
                problems = check_output(reply)  # 답변 검사기: 금지 문장·지어낸 조문·프롬프트 유출
                # 첫 질문에 확인 도구를 한 번도 안 쓰고 길게 답했다면, 모델이 도구 호출을 못 한 것으로 본다
                if st.session_state.turns == 1 and not events and len(reply) > 300:
                    problems.append("도구를 쓰지 않은 긴 답변 (모델이 도구 호출을 지원하지 않을 수 있음)")
                if problems:
                    print(f"[답변 검사] 차단: {problems}")
                    fallback_used = "blocked"
                    reply, events = (basic_followup(user_text) if st.session_state.turns > 1
                                     else basic_answer(user_text))
                    history = st.session_state.history + [{"role": "assistant", "content": reply}]
            except Exception as e:  # API 한도 초과·키 없음·네트워크 오류 → 규칙 기반 기본 안내
                import traceback
                traceback.print_exc()  # 터미널에 전체 오류 출력
                print(f"[기본 안내 모드] {type(e).__name__}: {str(e)[:200]}")
                fallback_used = "error"
                if st.session_state.turns > 1:
                    reply, events = basic_followup(user_text)
                else:
                    reply, events = basic_answer(user_text)
                history = st.session_state.history + [{"role": "assistant", "content": reply}]
        events = prepare_events(events, reply)
        render_assistant(events, reply, fallback=fallback_used)

    st.session_state.history = history
    st.session_state.display.append({"role": "assistant", "content": reply, "events": events, "fallback": fallback_used})
    st.rerun()  # 저장 버튼이 새 답변 기준으로 보이도록
