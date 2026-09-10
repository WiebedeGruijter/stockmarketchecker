from __future__ import annotations

from bs4 import BeautifulSoup

import scraper


def test_parse_price_nl_format():
    assert scraper.parse_price("€ 1.795,- per maand") == 1795.0
    assert scraper.parse_price("€ 950,00") == 950.0
    assert scraper.parse_price("no price") is None


def test_fetch_listings_accepts_selector_lists_and_fallbacks():
    html = """
    <html>
      <body>
        <article class="property-card">
          <h3 class="property-card__title">Herengracht 123</h3>
          <div class="property-card__price">€ 1.795,-</div>
          <a href="/nl/huur/123">Meer info</a>
        </article>
      </body>
    </html>
    """

    site = {
        "listing_url": "https://example.com/search",
        "base_url": "https://example.com",
        "listing_selector": ["article.property-card", ".listing"],
        "title_selector": ["h3", ".title"],
        "price_selector": [".property-card__price", ".price"],
        "link_selector": ["a[href]", ".link"],
        "link_attr": "href",
        "filters": {"max_price": 2000},
    }

    items = scraper.fetch_listings(site, html=html)

    assert len(items) == 1
    assert items[0]["title"] == "Herengracht 123"
    assert items[0]["price"] == 1795.0
    assert items[0]["url"] == "https://example.com/nl/huur/123"


def test_passes_filters_rejects_too_expensive_listing():
  filters = {"city": "Amsterdam", "max_price": 2000}
  assert scraper.passes_filters({"price": 2200, "city": "Amsterdam"}, filters) is False
  assert scraper.passes_filters({"price": 1800, "city": "Amsterdam"}, filters) is True
  assert scraper.passes_filters({"price": 2000, "city": "Amsterdam"}, filters) is False


def test_passes_filters_rejects_missing_required_fields():
  filters = {"city": "Amsterdam", "max_price": 1500}
  assert scraper.passes_filters({"price": 1200}, filters) is False
  assert scraper.passes_filters({"city": "Amsterdam"}, filters) is False


def test_fetch_listings_uses_root_anchor_as_vbt_listing_link():
  html = """
  <a class="property" href="/woning/amsterdam-example">
    <div class="items">
    <span class="normal">Examplestraat 1</span>
    <div class="price">€ 1.200,-</div>
    <div>Amsterdam</div>
    </div>
  </a>
  """
  items = scraper.fetch_listings({
    "listing_url": "https://example.com/woningen?city=amsterdam",
    "base_url": "https://example.com",
    "listing_selector": "a.property",
    "title_selector": ".normal",
    "price_selector": ".price",
    "city_selector": ".items > div:last-child",
    "link_selector": "a.property",
    "link_attr": "href",
  }, html=html)

  assert items[0]["id"] == "https://example.com/woning/amsterdam-example"
  assert items[0]["url"] == "https://example.com/woning/amsterdam-example"


def test_check_site_notifies_only_once_for_each_listing():
  site = {
    "name": "test-site",
    "listing_url": "https://example.com/woningen",
    "filters": {"city": "Amsterdam", "max_price": 1500},
  }
  config = {"notify": {"channels": ["email"]}}
  state = {}
  listings = [{
    "id": "listing-1",
    "title": "Nieuwe woning",
    "price_text": "€ 1.200,-",
    "price": 1200,
    "city": "Amsterdam",
    "url": "https://example.com/woning/1",
  }]
  notifications = []
  original_fetch = scraper.fetch_listings
  original_send = scraper.notify.send
  scraper.fetch_listings = lambda current_site: listings
  scraper.notify.send = lambda *args, **kwargs: notifications.append(kwargs)
  try:
    assert scraper.check_site(site, state, config) == 1
    assert scraper.check_site(site, state, config) == 0
  finally:
    scraper.fetch_listings = original_fetch
    scraper.notify.send = original_send

  assert len(notifications) == 1
  assert state["test-site"] == ["listing-1"]



def test_fetch_vanderlinden_listings_from_html():
    items = scraper.fetch_listings({
        "listing_url": "https://example.com/woning-huren/",
        "base_url": "https://example.com",
        "listing_selector": ".woninginfo",
        "title_selector": "strong",
        "price_selector": ".mt-2",
        "city_selector": ".text-80.mb-0",
        "link_selector": "a.blocklink",
        "link_attr": "href",
    }, html="""
      <div class="woninginfo">
        <div class="p-2">
          <strong>Teststraat 1</strong>
          <div class="text-80 mb-0">Amsterdam</div>
          <div class="mt-2">€ 1.250 per maand</div>
          <a class="blocklink" href="/huurwoning/test/1/"></a>
        </div>
      </div>
    """)

    assert items[0]["title"] == "Teststraat 1"
    assert items[0]["city"] == "Amsterdam"
    assert items[0]["price"] == 1250.0
    assert items[0]["url"] == "https://example.com/huurwoning/test/1/"


def test_fetch_schep_listings_from_api():
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [{
                "id": 123,
                "title": "Testwoning 2",
                "slug": "testwoning-2",
                "address": {"location": "Amsterdam"},
                "handover": {"price": 1400, "price_formatted": "€ 1.400"},
            }]}

    original_get = scraper.requests.get
    scraper.requests.get = lambda *args, **kwargs: Response()
    try:
        items = scraper.fetch_listings_schep({
            "api_url": "https://example.com/api",
            "base_url": "https://example.com",
            "api_params": {},
            "listing_url": "https://example.com/huur/woningen",
        })
    finally:
        scraper.requests.get = original_get

    assert items[0]["id"] == "123"
    assert items[0]["price"] == 1400.0
    assert items[0]["city"] == "Amsterdam"
    assert items[0]["url"] == "https://example.com/huur/woningen/testwoning-2"


def test_fetch_rebo_listings_from_algolia():
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"hits": [{
                "objectID": "entry:1",
                "title": "Testwoning 3, Amsterdam",
                "city": "Amsterdam",
                "price": 1350,
                "price_type": "per maand",
                "uri": "/aanbod/testwoning-3",
            }]}

    original_post = scraper.requests.post
    scraper.requests.post = lambda *args, **kwargs: Response()
    try:
        items = scraper.fetch_listings_algolia({
            "api_url": "https://example.com/algolia",
            "application_id": "app",
            "api_key": "key",
            "api_payload": {},
            "base_url": "https://example.com",
            "url_prefix": "nl",
            "listing_url": "https://example.com/huren",
        })
    finally:
        scraper.requests.post = original_post

    assert items[0]["id"] == "entry:1"
    assert items[0]["price"] == 1350.0
    assert items[0]["city"] == "Amsterdam"
    assert items[0]["url"] == "https://example.com/nl/aanbod/testwoning-3"
