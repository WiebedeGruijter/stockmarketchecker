import json

from huurwatcher.scraper import (
    build_ikwilhuren_search_payload,
    count_matching_listings,
    fetch_listings,
)


def test_build_ikwilhuren_search_payload_uses_city_and_max_price():
    payload = build_ikwilhuren_search_payload(
        csrf_token="abc123",
        city="Amsterdam",
        max_price=1500,
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
    assert payload["selPrijsTot"] == "1500"
    assert payload["selAfstand"] == "5"
    assert payload["selPrijsVan"] == ""


def test_fetch_listings_parses_ikwilhuren_filtered_html_without_recursing():
    html = '''
    <html><body>
      <article class="card-woning">
        <a class="card-title" href="/object/amsterdam-123-test/">Appartement Test</a>
        <span class="fw-bold">€ 1.450,- /mnd</span>
        <span>Amsterdam</span>
      </article>
    </body></html>
    '''
    items = fetch_listings({
        'name': 'ikwilhuren',
        'listing_url': 'https://ikwilhuren.nu/aanbod/',
        'listing_selector': '.card-woning',
        'title_selector': '.card-title',
        'price_selector': '.fw-bold',
        'city_selector': 'span:nth-of-type(2)',
        'link_selector': '.card-title',
        'link_attr': 'href',
        'base_url': 'https://ikwilhuren.nu',
        'filters': {'city': 'Amsterdam', 'max_price': 1750},
    }, html=html)
    assert len(items) == 1
    assert items[0]['title'] == 'Appartement Test'
    assert items[0]['price'] == 1450.0
    assert items[0]['city'] == 'Amsterdam'


def test_count_matching_listings_counts_only_matching_filtered_items():
    html = '''
    <html><body>
      <article class="card-woning">
        <a class="card-title" href="/object/amsterdam-123-test/">Appartement Test</a>
        <span class="fw-bold">€ 1.450,- /mnd</span>
        <span>Amsterdam</span>
      </article>
      <article class="card-woning">
        <a class="card-title" href="/object/utrecht-999/">Appartement Utrecht</a>
        <span class="fw-bold">€ 1.200,- /mnd</span>
        <span>Utrecht</span>
      </article>
      <article class="card-woning">
        <a class="card-title" href="/object/amsterdam-222/">Appartement Te duur</a>
        <span class="fw-bold">€ 2.500,- /mnd</span>
        <span>Amsterdam</span>
      </article>
    </body></html>
    '''
    count = count_matching_listings({
        'name': 'ikwilhuren',
        'listing_url': 'https://ikwilhuren.nu/aanbod/',
        'listing_selector': '.card-woning',
        'title_selector': '.card-title',
        'price_selector': '.fw-bold',
        'city_selector': 'span:nth-of-type(2)',
        'link_selector': '.card-title',
        'link_attr': 'href',
        'base_url': 'https://ikwilhuren.nu',
        'filters': {'city': 'Amsterdam', 'max_price': 1500},
    }, html=html)
    assert count == 1
