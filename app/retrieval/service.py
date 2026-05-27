from app.retrieval.embedding import embed_text
from app.storage.vector_store import search_items
import json


def _decode_metadata(value: object) -> object:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value or {}


def _decode_tags(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str):
        return [item for item in value.split(",") if item]
    return []


def search_context(
    query: str,
    top_k: int = 5,
    cube_id: str | None = None,
    cube_ids: list[str] | None = None,
    context_domain: str | None = None,
    kind: str | None = None,
    mode: str = "context_search",
    legacy_flat: bool = False,
    context_budget_chars: int = 12000,
) -> dict:
    if mode == "memory_search":
        context_domain = "memory"
        kind = "memory"
    elif mode == "document_search":
        kind = "chunk"
    elif mode == "asset_search":
        context_domain = "asset"
        kind = "asset"
    scoped_cube_ids = cube_ids or ([cube_id] if cube_id else None)
    results = search_items(query, top_k, kind=kind, context_domain=context_domain, cube_ids=scoped_cube_ids)
    cleaned = []
    for row in results:
        metadata = _decode_metadata(row.get("metadata"))
        cleaned.append(
            {
                "id": row.get("id"),
                "kind": row.get("kind"),
                "cube_id": row.get("cube_id") or metadata.get("cube_id"),
                "context_domain": row.get("context_domain") or metadata.get("context_domain"),
                "text": row.get("text"),
                "source": row.get("source"),
                "doc_id": row.get("doc_id"),
                "chunk_index": row.get("chunk_index"),
                "tags": _decode_tags(row.get("tags")),
                "agent_id": row.get("agent_id"),
                "conversation_id": row.get("conversation_id"),
                "status": row.get("status") or metadata.get("status"),
                "source_kind": row.get("source_kind") or metadata.get("source_kind"),
                "trust_level": row.get("trust_level") or metadata.get("trust_level"),
                "metadata": metadata,
                "score": float(1.0 / (1.0 + max(row.get("_distance", 0.0), 0.0))),
            }
        )
    budget = _budget_metadata(cleaned, context_budget_chars)
    if legacy_flat or mode != "context_search" or context_domain or kind:
        budgeted = _apply_context_budget(cleaned, context_budget_chars)
        return {
            "query": query,
            "mode": mode,
            "context_domain": context_domain,
            "kind": kind,
            "results": budgeted,
            "budget": _budget_metadata(budgeted, context_budget_chars, original_used_chars=budget["original_used_chars"]),
        }
    groups = {"memory": [], "document": [], "asset": [], "session": []}
    budgeted = _apply_context_budget(cleaned, context_budget_chars)
    for item in budgeted:
        domain = item.get("context_domain")
        if domain == "session" or item.get("kind") == "session_event":
            groups["session"].append(item)
        elif domain == "asset" or item.get("kind") == "asset":
            groups["asset"].append(item)
        elif domain == "memory" or item.get("kind") == "memory":
            groups["memory"].append(item)
        else:
            groups["document"].append(item)
    return {
        "query": query,
        "mode": mode,
        "groups": groups,
        "budget": _budget_metadata(budgeted, context_budget_chars, original_used_chars=budget["original_used_chars"]),
    }


def _apply_context_budget(items: list[dict], context_budget_chars: int) -> list[dict]:
    kept = []
    used = 0
    for item in items:
        item_cost = _item_cost(item)
        if kept and used + item_cost > context_budget_chars:
            break
        if not kept and item_cost > context_budget_chars:
            trimmed = {**item}
            text = str(trimmed.get("text") or "")
            available = max(context_budget_chars - _item_cost({**trimmed, "text": ""}), 0)
            trimmed["text"] = text[:available]
            trimmed["truncated"] = True
            kept.append(trimmed)
            break
        kept.append(item)
        used += item_cost
    return kept


def _budget_metadata(items: list[dict], requested_chars: int, original_used_chars: int | None = None) -> dict:
    used_chars = sum(_item_cost(item) for item in items)
    original = used_chars if original_used_chars is None else original_used_chars
    return {
        "requested_chars": requested_chars,
        "used_chars": min(used_chars, requested_chars),
        "original_used_chars": original,
        "truncated": original > requested_chars or len(items) == 0 and original > 0 or any(item.get("truncated") for item in items),
    }


def _item_cost(item: dict) -> int:
    text = str(item.get("text") or "")
    metadata = item.get("metadata") or {}
    source = str(item.get("source") or "")
    return len(text) + len(source) + len(json.dumps(metadata, ensure_ascii=False))


def run_retrieval_eval(cases: list[dict], top_k: int = 5) -> dict:
    evaluated = []
    domain_hits = 0
    id_hits = 0
    for case in cases:
        query = str(case.get("query") or "")
        expected_domain = case.get("expected_domain")
        expected_id = case.get("expected_id")
        result = search_context(query, top_k=top_k, mode="context_search")
        groups = result.get("groups", {})
        domain_results = groups.get(expected_domain, []) if expected_domain else []
        domain_hit = bool(domain_results)
        id_hit = False
        if expected_id:
            id_hit = any(_matches_expected_id(item, str(expected_id)) for group in groups.values() for item in group)
        if domain_hit:
            domain_hits += 1
        if id_hit:
            id_hits += 1
        evaluated.append(
            {
                "query": query,
                "expected_domain": expected_domain,
                "expected_id": expected_id,
                "domain_hit": domain_hit,
                "id_hit": id_hit,
                "top_ids": [item.get("id") for group in groups.values() for item in group][:top_k],
                "top_domains": {
                    domain: [item.get("id") for item in items[:top_k]]
                    for domain, items in groups.items()
                    if items
                },
            }
        )
    total = len(evaluated)
    return {
        "summary": {
            "total": total,
            "domain_hits": domain_hits,
            "id_hits": id_hits,
            "domain_hit_rate": domain_hits / total if total else 0,
            "id_hit_rate": id_hits / total if total else 0,
        },
        "cases": evaluated,
    }


def _matches_expected_id(item: dict, expected_id: str) -> bool:
    return expected_id in {
        str(item.get("id") or ""),
        str(item.get("asset_id") or ""),
        str(item.get("doc_id") or ""),
        str((item.get("metadata") or {}).get("asset_id") or ""),
    }
