"""Small read-only conversation window for the isolated public demo."""

MAX_HISTORY = 3
WRITE_HINTS = ("보내", "메일", "완료 처리", "완료처리", "변경", "삭제")


def is_read_only_question(question):
    return (
        isinstance(question, str)
        and 0 < len(question.strip()) <= 400
        and not any(hint in question for hint in WRITE_HINTS)
    )


def safe_history(items):
    if not isinstance(items, list):
        return []
    return [
        item.strip() for item in items
        if is_read_only_question(item)
    ][-MAX_HISTORY:]
