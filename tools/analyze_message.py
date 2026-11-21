"""문자·메일·통화 메모에서 기관명, 연락처, 요구사항, 사칭 신호를 뽑는다.

LLM을 부르지 않는 규칙 기반 도구다. (API 호출 수를 줄이고, 판정 근거를 설명할 수 있게)
"""
import re

from .data_loader import load

PHONE_RE = re.compile(r"(0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}|(?<!\d)1\d{2,3}(?!\d))")
URL_RE = re.compile(r"(https?://\S+|www\.\S+|\b[\w-]+\.(?:com|kr|net|xyz|top|cc|io|me|ly)(?:/\S*)?)", re.I)
# 연도(19xx·20xx)로 시작하는 것만 사건번호로 본다 (1588-1234 같은 대표번호 오인 방지)
CASE_NO_RE = re.compile(r"(?<!\d)(?:19|20)\d{2}\s*(?:-\s*\d{4,7}|(?:형제|고단|고합|고소|진정|수사|내사|조사)\s*\d+)(?!\d)")
def _is_gov_url(url):
    host = re.sub(r"^https?://", "", url, flags=re.I).split("/")[0].split("?")[0].split(":")[0].lower().rstrip(".")
    return host == "go.kr" or host.endswith(".go.kr")


ROLE_WORDS = {"피의자": "피의자", "피고소인": "피의자", "참고인": "참고인", "피해자": "피해자", "고소인": "피해자"}


def analyze_message(text: str) -> dict:
    lowered = text.lower()
    agencies = load("agencies")
    rules = load("scam_rules")

    phones = sorted(set(m.group(0) for m in PHONE_RE.finditer(text)))
    urls = sorted(set(m.group(0) for m in URL_RE.finditer(text)))
    # 정부 공식 주소(.go.kr)는 링크가 있어도 사칭 신호로 보지 않는다 (예: police.go.kr, kics.go.kr)
    # 주소의 호스트 부분이 .go.kr로 '끝나야' 공식으로 본다 (police.go.kr.xyz.com 같은 위장 주소 차단)
    unofficial_urls = [u for u in urls if not _is_gov_url(u)]
    case_numbers = sorted(set(m.group(0) for m in CASE_NO_RE.finditer(text)))
    roles = sorted({v for k, v in ROLE_WORDS.items() if k in text})

    orgs = []
    for ag in agencies["agencies"]:
        names = [ag["name"], *ag["aliases"]]
        if any(n in text for n in names):
            orgs.append(ag["name"])
    fake_orgs = [f["name"] for f in agencies["known_fake_orgs"] if f["name"] in text]

    signals, score, critical = [], 0, False
    for rule in rules["rules"]:
        if rule["id"] == "fake_org":
            hit = bool(fake_orgs)
            matched = fake_orgs
        elif rule["id"] == "ai_instruction":
            from guard import ai_directive_matches  # 순환 import를 피하려고 여기서 불러온다

            matched = ai_directive_matches(text)
            hit = bool(matched)
        else:
            matched = [kw for kw in rule["keywords"] if kw.lower() in lowered]
            hit = bool(matched)
        if rule["id"] == "file_or_link_document" and unofficial_urls:
            hit, matched = True, matched + ["(공식 주소가 아닌 링크)"]
        if hit:
            signals.append({"id": rule["id"], "label": rule["label"], "matched": matched, "why": rule["why"]})
            score += rule["weight"]
            critical = critical or rule["critical"]

    th = rules["thresholds"]
    if critical or score >= th["high"]:
        verdict = "high"
        verdict_label = "사칭 의심 높음"
    elif score >= th["check"]:
        verdict = "check"
        verdict_label = "확인 필요"
    else:
        verdict = "low"
        verdict_label = "사칭 신호 없음"

    return {
        "verdict": verdict,
        "verdict_label": verdict_label,
        "score": score,
        "signals": signals,
        "extracted": {
            "orgs": orgs,
            "fake_orgs": fake_orgs,
            "phones": phones,
            "urls": urls,
            "case_numbers": case_numbers,
            "roles": roles,
        },
        "advice": (
            "링크·파일을 열지 말고, 받은 번호로 다시 걸지 말고, 112에 신고하세요."
            if verdict == "high"
            else "통화한 수사관이 맞는지 경찰민원콜센터 182에 소속과 이름을 말해 확인하세요."
        ),
    }
