"""
비정형 데이터 저장소 (회의록 원문/요약, 사내 규정 등).
Chroma가 설치되어 있으면 실제 임베딩 검색을, 없으면 간단한 키워드 매칭으로 폴백합니다.
(데모 환경에서 의존성 설치 없이도 바로 동작하게 하기 위함)
"""
from config import VECTOR_DB_DIR, MOCK_MODE

try:
    import chromadb
    _HAS_CHROMA = True
except ImportError:
    _HAS_CHROMA = False

_fallback_store: list[dict] = []  # [{"id": ..., "text": ..., "metadata": {...}}]


def _get_chroma_collection():
    client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
    return client.get_or_create_collection("meeting_docs")


def add_document(doc_id: str, text: str, metadata: dict | None = None):
    metadata = metadata or {}
    if _HAS_CHROMA and not MOCK_MODE:
        collection = _get_chroma_collection()
        collection.add(ids=[doc_id], documents=[text], metadatas=[metadata])
    else:
        _fallback_store.append({"id": doc_id, "text": text, "metadata": metadata})


def search(query: str, top_k: int = 3) -> list[dict]:
    """질의와 관련된 문서를 top_k개 반환. [{"id", "text", "metadata", "score"}]"""
    if _HAS_CHROMA and not MOCK_MODE:
        collection = _get_chroma_collection()
        result = collection.query(query_texts=[query], n_results=top_k)
        hits = []
        for i in range(len(result["ids"][0])):
            hits.append({
                "id": result["ids"][0][i],
                "text": result["documents"][0][i],
                "metadata": result["metadatas"][0][i],
                "score": result["distances"][0][i] if result.get("distances") else None,
            })
        return hits

    # --- 폴백: 아주 단순한 키워드 겹침 스코어링 ---
    query_terms = set(query.replace("?", "").split())
    scored = []
    for doc in _fallback_store:
        doc_terms = set(doc["text"].split())
        overlap = len(query_terms & doc_terms)
        if overlap > 0:
            scored.append({**doc, "score": overlap})
    scored.sort(key=lambda d: d["score"], reverse=True)
    return scored[:top_k]
