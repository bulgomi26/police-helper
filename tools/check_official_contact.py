"""기관명·전화번호를 공식 확인 경로와 대조한다.

번호는 사용자가 실제로 알려 준 경우에만 대조한다.
결과 문장은 '모른다'가 아니라 '무엇을 하면 되는지'로 쓴다.
"""
import re

from .data_loader import load


def _digits(s):
    return re.sub(r"\D", "", s or "")


def check_official_contact(org_name: str = "", phone: str = "") -> dict:
    data = load("agencies")
    phone = (phone or "").strip()
    result = {"org_name": org_name, "phone": phone or None}

    fake = next((f for f in data["known_fake_orgs"] if org_name and f["name"] in org_name), None)
    if fake:
        result.update(
            status="fake_org",
            message=f"'{fake['name']}'은(는) 실제로 없는 조직 이름입니다. 사칭이니 응하지 말고 112에 신고하세요.",
            note=fake["note"],
        )
        return result

    agency = None
    for ag in data["agencies"]:
        if org_name and any(n in org_name for n in [ag["name"], *ag["aliases"]]):
            agency = ag
            break

    if not agency:
        result.update(
            status="unknown_org",
            message="기관 공식 홈페이지에 나온 대표번호로 직접 전화해, 연락한 사람의 소속과 이름을 확인하세요.",
        )
        return result

    result.update(
        agency=agency["name"],
        short_name=agency.get("short_name", agency["name"]),
        tips=agency.get("tips", []),
        official_numbers=agency["official_numbers"],
        extra_contacts=agency.get("extra_contacts", {}),
        how_to_verify=agency["how_to_verify"],
        verify_steps=agency.get("verify_steps", []),
        web_tip=agency.get("web_tip", ""),
        next_call_tip=agency.get("next_call_tip", ""),
        data_verified=agency["verified"],
    )

    # 번호로 진짜·가짜를 판정하지 않는다.
    # - 경찰서마다 번호가 달라 전국 번호 목록으로는 맞는 번호도 '아니다'로 나올 수 있고
    # - 발신번호는 조작될 수 있어 대표번호와 같아도 진짜라고 할 수 없다.
    if not phone:
        result.update(status="no_phone", message="아래 순서로 연락한 사람이 실제 수사관인지 확인하세요.")
    elif _digits(phone) in [_digits(n) for n in agency["official_numbers"]]:
        result.update(
            status="matched",
            message="공식 번호로 표시된 연락이지만, 발신번호는 조작될 수 있으니 아래 순서로 한 번 더 확인하세요.",
        )
    else:
        result.update(
            status="verify_needed",
            message="받은 번호가 실제 수사관 번호인지 아래 순서로 확인하세요.",
        )
    return result
