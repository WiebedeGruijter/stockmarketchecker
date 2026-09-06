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
    assert scraper.passes_filters({"price": 2200}, {"max_price": 2000}) is False
    assert scraper.passes_filters({"price": 1800}, {"max_price": 2000}) is True
