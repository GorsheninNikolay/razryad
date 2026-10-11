def create_shortlist(need_id: str, employer_id: str, filters: dict) -> dict:
    """Create a new shortlist snapshot."""
    shortlist_id = "sl_123"
    revision_id = "rev_1"
    
    return {
        "shortlist_id": shortlist_id,
        "current_revision": revision_id,
        "need_id": need_id,
        "employer_id": employer_id,
        "filters": filters
    }

def update_shortlist_filters(shortlist: dict, new_filters: dict) -> dict:
    """Refine filters, creating a new revision."""
    new_rev = "rev_2"
    return {
        "shortlist_id": shortlist["shortlist_id"],
        "current_revision": new_rev,
        "need_id": shortlist["need_id"],
        "employer_id": shortlist["employer_id"],
        "filters": new_filters
    }

def freeze_candidate(shortlist_id: str, candidate_id: str):
    pass
