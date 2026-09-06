import json

from huurwatcher.scraper import build_ikwilhuren_search_payload


def test_build_ikwilhuren_search_payload_uses_city_and_max_price():
    payload = build_ikwilhuren_search_payload(
        csrf_token="abc123",
        city="Amsterdam",
        max_price=1750,
        radius=5,
        location={"weergavenaam": "Gemeente Amsterdam", "lat": 52.372363, "lng": 4.901512},
    )

    assert payload["_token"] == "abc123"
    assert payload["selAdres"] == "Gemeente Amsterdam"
    assert payload["postrequest"] == "doeZoek"
    assert payload["objSearch"] == json.dumps({
        "weergavenaam": "Gemeente Amsterdam",
        "lat": 52.372363,
        "lng": 4.901512,
    })
    assert payload["selPrijsTot"] == "1750"
    assert payload["selAfstand"] == "5"
    assert payload["selPrijsVan"] == ""
