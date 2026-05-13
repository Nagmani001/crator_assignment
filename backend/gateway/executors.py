from .models import Action


_MOCK_PAGES = {
    "p1": {"id": "p1", "title": "Roadmap", "content": "Q3 plan"},
    "p2": {"id": "p2", "title": "Notes", "content": "Standup notes"},
}


def run(action: Action, params: dict) -> dict:
    key = (action.toolkit.slug, action.slug)
    handler = _HANDLERS.get(key)
    if handler is None:
        return {"ok": True, "note": f"no mock handler for {key}", "params": params}
    return handler(params)


def _notion_read_page(params):
    page_id = params.get("page_id", "p1")
    page = _MOCK_PAGES.get(page_id, {"id": page_id, "title": "Unknown", "content": ""})
    return {"page": page}


def _notion_update_page(params):
    return {
        "page_id": params.get("page_id"),
        "updated_fields": list((params.get("fields") or {}).keys()),
        "updated": True,
    }


def _notion_delete_page(params):
    return {"page_id": params.get("page_id"), "deleted": True}


_HANDLERS = {
    ("notion", "read_page"): _notion_read_page,
    ("notion", "update_page"): _notion_update_page,
    ("notion", "delete_page"): _notion_delete_page,
}
