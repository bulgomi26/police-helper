"""LLM 도구 호출 루프.

LLM이 도구를 부르면 실행해서 결과를 돌려주고, 최종 답을 낼 때까지 반복한다.
어떤 도구를 부를지, 무엇을 되물을지는 LLM이 정한다(에이전트).
도구는 결정론적 Python이라 판정 근거가 데이터에 남는다(환각 억제).
"""
import json
import re
import time
from pathlib import Path

from tools import TOOLS, run_tool

SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.md").read_text(encoding="utf-8")


def make_client(settings, max_retries=1):
    from openai import OpenAI  # 테스트에서는 가짜 클라이언트를 넣으므로 여기서만 import

    # 요청 1번에 최대 30초, 재시도 1번. 오래 기다리게 하느니 빨리 기본 안내로 바꾼다
    return OpenAI(base_url=settings["base_url"], api_key=settings["api_key"], max_retries=max_retries, timeout=30)


THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def clean_text(text):
    """일부 Qwen 모델이 붙이는 생각 과정(<think>…</think>)을 지운다."""
    return THINK_RE.sub("", text or "").strip()


def compact_history(history):
    """토큰 절약: 지난 턴의 도구 호출·결과는 빼고, 사용자 말과 최종 답변만 남긴다. 최근 6개 메시지만 보낸다."""
    kept = [m for m in history if m["role"] == "user" or (m["role"] == "assistant" and not m.get("tool_calls"))]
    return kept[-6:]


def _assistant_dict(msg):
    """SDK 응답 메시지를 다음 요청에 넣을 dict로 바꾼다."""
    d = {"role": "assistant", "content": msg.content or ""}
    if getattr(msg, "tool_calls", None):
        d["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]
    return d


class Agent:
    def __init__(self, client, model, max_steps=6, temperature=0.2, time_limit=None, max_tokens=2000,
                 extra_body=None):
        self.max_tokens = max_tokens
        self.extra_body = extra_body  # 제공자별 추가 옵션 (예: Alibaba 생각 모드 끄기)
        self.time_limit = time_limit  # 초. 넘으면 TimeoutError → 앱에서 기본 안내로 바꾼다
        self.client = client
        self.model = model
        self.max_steps = max_steps
        self.temperature = temperature

    def run(self, history, forced_tools=None, stop_after_forced=False):
        """history: 지금까지의 대화(user/assistant/tool 메시지 dict 목록).

        반환: (최종 답변 문자열, 이번 턴에 실행된 도구 이벤트 목록, 갱신된 history)
        """
        messages = compact_history(history)
        events = []
        self.tokens = 0
        start = time.time()
        for step in range(self.max_steps):
            if self.time_limit and time.time() - start > self.time_limit:
                raise TimeoutError(f"답변 시간이 {self.time_limit}초를 넘었습니다.")
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, *messages],
                tools=TOOLS,
                # 첫 질문의 첫 단계는 정해진 도구를 반드시 부르게 한다 (모델이 도구 없이 지어내 답하는 것 방지)
                # 첫 질문은 정해진 도구를 차례로 반드시 부르게 한다 (도구 없이 지어내 답하는 것 방지)
                tool_choice=({"type": "function", "function": {"name": forced_tools[step]}}
                             if forced_tools and step < len(forced_tools) else "auto"),
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                **({"extra_body": self.extra_body} if self.extra_body else {}),
            )
            self.calls = getattr(self, "calls", 0) + 1
            usage = getattr(resp, "usage", None)
            self.tokens += getattr(usage, "total_tokens", 0) or 0
            msg = resp.choices[0].message
            msg.content = clean_text(msg.content)
            messages.append(_assistant_dict(msg))

            if not getattr(msg, "tool_calls", None):
                return msg.content or "", events, messages

            for tc in msg.tool_calls:
                result = run_tool(tc.function.name, tc.function.arguments)
                events.append({"tool": tc.function.name, "args": tc.function.arguments, "result": result})
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, ensure_ascii=False)}
                )
            if stop_after_forced and forced_tools and step == len(forced_tools) - 1:
                return "", events, messages  # 답변 본문은 앱이 검증된 데이터로 조립한다

        fallback = "확인할 내용이 많아 여기서 정리할게요. 위 카드 내용을 먼저 확인해 주시고, 이어서 궁금한 점을 말씀해 주세요."
        messages.append({"role": "assistant", "content": fallback})
        return fallback, events, messages
