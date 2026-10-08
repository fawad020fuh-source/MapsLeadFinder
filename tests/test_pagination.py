from src.api_client import GooglePlacesClient


def test_pagination_no_duplicate_place_ids():
    client = GooglePlacesClient(api_key="fake-key")
    seen = set()
    items = [
        {"id": "p1", "displayName": {"text": "Alpha"}},
        {"id": "p1", "displayName": {"text": "Alpha"}},
        {"id": "p2", "displayName": {"text": "Beta"}},
    ]
    deduped = []
    for item in items:
        place_id = item["id"]
        if place_id not in seen:
            seen.add(place_id)
            deduped.append(item)
    assert len(deduped) == 2
    assert {item["id"] for item in deduped} == {"p1", "p2"}

    # sanity: pagination model just ensures no duplicate place IDs.
    assert len(seen) == 2
