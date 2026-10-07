"""
엔티티 정규화: LLM이 뽑은 담당자 이름(예: "김대리")을
실제 people 테이블의 레코드로 매핑합니다.

정확히 일치하면 자동 매핑, 모호하거나 없으면 후보를 제시하고 보류(None) 처리합니다.
-> main.py 의 승인 단계에서 사람이 최종 확인하도록 흐름을 넘깁니다.
"""
import db


def resolve_assignee(raw_name: str) -> dict:
    """
    반환: {"status": "matched", "person": Row} |
          {"status": "ambiguous", "candidates": [Row, ...]} |
          {"status": "unresolved"}
    """
    exact = db.find_person_by_name(raw_name)
    if exact:
        return {"status": "matched", "person": exact}

    # 정확히 일치하는 사람이 없으면, 이름에서 직급을 뗀 부분 문자열로 후보 탐색
    # (예: "김대리" -> "김" 으로 느슨하게 검색하는 매우 단순한 휴리스틱)
    core_name = raw_name[0] if raw_name else raw_name
    candidates = db.search_candidates_by_partial_name(core_name)

    if len(candidates) == 1:
        return {"status": "matched", "person": candidates[0]}
    elif len(candidates) > 1:
        return {"status": "ambiguous", "candidates": candidates}
    else:
        return {"status": "unresolved"}


def review_and_confirm_extraction(extracted: dict, auto_approve: bool = True) -> dict:
    """
    Human-in-the-loop 검증 단계.
    실제 서비스라면 여기서 UI로 사용자에게 요약/업무 목록을 보여주고 수정받습니다.
    데모에서는 콘솔에 무엇을 확인받는지 출력하고, auto_approve=True 면 그대로 승인합니다.
    """
    print("\n[검증 요청] 아래 추출 결과를 확인해주세요:")
    print(f"  - 제목: {extracted['title']}")
    print(f"  - 요약: {extracted['summary']}")
    for t in extracted["tasks"]:
        print(f"  - 업무: {t['assignee']} / {t['description']} / 마감 {t['due_date']}")

    if auto_approve:
        print("[검증 완료] 자동 승인 처리됨 (데모 모드)\n")
        return extracted

    # 실제로는 여기서 input() 이나 웹 UI 콜백으로 수정된 내용을 받아 병합합니다.
    return extracted
