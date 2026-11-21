"""설정 값 읽기.

우선순위: Streamlit secrets(배포 환경) → 환경변수(로컬) → 기본값.
LLM 제공자는 OpenAI 호환 API라서 주소(base_url)와 모델 이름만 바꾸면 된다.
"""
import os
from pathlib import Path

PROVIDERS = {
    # Alibaba Cloud Model Studio (국제/싱가포르 리전).
    # 주의: qwen-plus는 싱가포르 리전에서 도구 호출(Function Calling)을 지원하지 않는다 (공식 모델 문서, 2026-11 확인).
    # 싱가포르에서 도구 호출이 지원되는 모델(qwen3.6-plus 등)을 쓰고, 무료 할당량이 있는지 콘솔에서 확인할 것.
    "alibaba": {
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen3.6-plus",
        # qwen3.6-plus는 '깊은 생각(thinking)'이 기본으로 켜져 있어 느리고 토큰을 많이 쓴다 → 끈다
        # (도구 선택·답변 정리에는 필요 없음, 무료 한도 절약)
        "extra_body": {"enable_thinking": False},
    },
    # Groq 무료 플랜 (카드 불필요). Qwen 모델 이름은 console.groq.com의 Models 목록에서 확인
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "qwen/qwen3.8-27b",
    },
    # OpenRouter 무료 모델 (테스트용). 무료 모델 목록은 예고 없이 바뀜 (2026-11 기준 무료 Qwen 없음).
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "nvidia/nemotron-3.5-super-vl:free",
    },
}


SECRETS_PATH = Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
_file_secrets = None


def _read_secrets_file():
    """streamlit 밖(테스트 스크립트)에서도 secrets.toml을 읽는다. 실행 위치와 상관없이 이 폴더 기준."""
    global _file_secrets
    if _file_secrets is None:
        _file_secrets = {}
        if SECRETS_PATH.exists():
            try:
                import tomllib

                with open(SECRETS_PATH, "rb") as f:
                    _file_secrets = tomllib.load(f)
            except Exception as e:  # 따옴표 빠짐 등 문법 오류를 알려 준다 (값은 출력하지 않음)
                print(f"[설정] {SECRETS_PATH} 를 읽지 못했습니다: {type(e).__name__}: {e}")
    return _file_secrets


def get_setting(name, default=None):
    try:
        import streamlit as st  # 배포 환경

        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    file_secrets = _read_secrets_file()
    if name in file_secrets:
        return file_secrets[name]
    return os.environ.get(name, default)


def llm_settings(prefix="LLM"):
    """prefix="LLM"이면 기본 제공자, "LLM_BACKUP"이면 예비 제공자 설정."""
    provider = get_setting(f"{prefix}_PROVIDER", "groq" if prefix == "LLM" else None)
    if not provider:
        return None
    preset = PROVIDERS.get(provider, PROVIDERS["groq"])
    return {
        "provider": provider,
        "base_url": get_setting(f"{prefix}_BASE_URL", preset["base_url"]),
        "api_key": get_setting(f"{prefix}_API_KEY"),
        "model": get_setting(f"{prefix}_MODEL", preset["default_model"]),
        "extra_body": preset.get("extra_body"),
    }


def llm_chain():
    """앞에서부터 차례로 시도할 제공자 목록. 기본 → 예비(설정했을 때만). 모두 실패하면 앱이 규칙 기반 기본 안내로 바꾼다."""
    chain = [llm_settings("LLM")]
    backup = llm_settings("LLM_BACKUP")
    if backup and backup.get("api_key"):
        chain.append(backup)
    return chain


# 공개 배포 시 비용·한도 보호용: 세션당 사용자 메시지 수 제한
MAX_TURNS_PER_SESSION = int(get_setting("MAX_TURNS_PER_SESSION", 15))
# 한 번의 사용자 메시지에서 에이전트가 도구를 부를 수 있는 최대 횟수
MAX_AGENT_STEPS = int(get_setting("MAX_AGENT_STEPS", 6))
# 한 번의 답변에 쓸 수 있는 최대 시간(초). 넘으면 기본 안내로 바꾼다 (심사위원이 오래 기다리지 않게)
TURN_TIME_LIMIT = int(get_setting("TURN_TIME_LIMIT", 60))
# 한 번 호출에서 받을 최대 답변 길이(토큰). 지정하지 않으면 일부 제공자(Groq)가 모델 최대치(수만 토큰)를
# 요청한 것으로 계산해 분당 한도를 넘었다고 거절한다 ("Request too large")
MAX_OUTPUT_TOKENS = int(get_setting("MAX_OUTPUT_TOKENS", 2000))
