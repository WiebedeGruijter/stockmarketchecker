"""
huurwatcher
-----------
Checkt een of meerdere verhuur-sites op nieuwe listings die aan je
criteria voldoen, en stuurt een notificatie zodra er iets nieuws is.

Gebruik:
    python scraper.py            # eenmalige check van alle enabled sites
    python scraper.py --loop     # blijft draaien, checkt elke N minuten
    python scraper.py --site vesteda   # check alleen die ene site

Zie README.md voor installatie en het invullen van de CSS-selectors.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
import yaml
from bs4 import BeautifulSoup

import notify

STATE_FILE = Path(__file__).parent / "seen.json"
CONFIG_FILE = Path(__file__).parent / "config.yaml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def load_config() -> dict:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    if not isinstance(config, dict):
        raise ValueError("config.yaml moet een YAML-mapping zijn.")
    config.setdefault("notify", {})
    config["notify"].setdefault("channels", ["mac"])
    config["notify"].setdefault("telegram", {})
    config.setdefault("sites", [])
    return config


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def parse_price(text: str) -> float | None:
    """Haalt een bedrag uit iets als '€ 1.795,- per maand' -> 1795.0."""
    if not text:
        return None
    match = re.search(r"[\d.,]+", text)
    if not match:
        return None
    raw = match.group(0)
    normalized = raw.replace(".", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def _selector_candidates(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split("|") if part.strip()]
    if isinstance(value, (list, tuple)):
        return [str(part).strip() for part in value if str(part).strip()]
    return []


def _find_matching_node(parent, selectors: Iterable[str]):
    for selector in selectors:
        if not selector:
            continue
        node = parent.select_one(selector)
        if node is not None:
            return node
    return None


def fetch_listings_api(site: dict) -> list[dict]:
    api_url = site.get("api_url")
    if not api_url:
        raise ValueError(f"Geen api_url ingesteld voor site '{site.get('name', 'onbekend')}'.")

    request_headers = {
        **HEADERS,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    method = (site.get("api_method") or "POST").upper()
    payload = dict(site.get("api_payload") or {})
    if not payload:
        payload = {
            "s": site.get("api_location") or "Amsterdam, Nederland",
            "placeType": site.get("api_place_type", 1),
            "rootId": site.get("api_root_id", 1303),
        }

    if method == "GET":
        resp = requests.get(api_url, params=payload, headers=request_headers, timeout=20)
    else:
        resp = requests.post(api_url, json=payload, headers=request_headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    if isinstance(data, dict):
        results = data.get("results")
        if isinstance(results, dict):
            objects = results.get("objects") or results.get("items") or []
        else:
            objects = data.get("objects") or data.get("items") or []
    else:
        objects = []

    items = []
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        street = obj.get("street") or ""
        house = obj.get("houseNumber") or ""
        city = obj.get("city") or ""
        title = f"{street} {house}".strip() or obj.get("complex") or obj.get("location") or "Onbekende woning"
        if city and title and city not in title:
            title = f"{title}, {city}"

        price_text = str(obj.get("price") or "")
        price = parse_price(price_text)
        url = obj.get("url") or ""
        if url and not url.startswith("http"):
            url = urljoin(site.get("base_url", site.get("listing_url", "https://www.vesteda.com")), url)
        if not url:
            url = site.get("listing_url", "")

        items.append({
            "id": str(obj.get("id") or url or title),
            "title": title,
            "price_text": price_text,
            "price": price,
            "city": str(obj.get("city") or obj.get("location") or ""),
            "url": url,
        })
    return items


def fetch_listings(site: dict, html: str | None = None) -> list[dict]:
    if site.get("api_url"):
        return fetch_listings_api(site)

    if html is None:
        resp = requests.get(site["listing_url"], headers=HEADERS, timeout=20)
        resp.raise_for_status()
        html = resp.text

    soup = BeautifulSoup(html, "lxml")

    listing_selectors = _selector_candidates(site.get("listing_selector"))
    if not listing_selectors:
        raise ValueError(f"Geen listing_selector ingesteld voor site '{site.get('name', 'onbekend')}'.")

    cards: list = []
    for selector in listing_selectors:
        found = soup.select(selector)
        if found:
            cards = found
            break

    if not cards:
        return []

    title_selectors = _selector_candidates(site.get("title_selector"))
    price_selectors = _selector_candidates(site.get("price_selector"))
    city_selectors = _selector_candidates(site.get("city_selector"))
    link_selectors = _selector_candidates(site.get("link_selector"))
    link_attr = site.get("link_attr", "href")
    base_url = site.get("base_url", site.get("listing_url", ""))

    items = []
    for card in cards:
        title_el = _find_matching_node(card, title_selectors)
        price_el = _find_matching_node(card, price_selectors)
        city_el = _find_matching_node(card, city_selectors)
        link_el = _find_matching_node(card, link_selectors)

        title = title_el.get_text(" ", strip=True) if title_el else "(geen titel gevonden)"
        price_text = price_el.get_text(" ", strip=True) if price_el else ""
        city = city_el.get_text(" ", strip=True) if city_el else ""
        href = link_el.get(link_attr) if link_el and link_attr in link_el.attrs else None
        if href and href.startswith("/"):
            url = urljoin(base_url, href)
        elif href:
            url = urljoin(base_url, href) if not href.startswith("http") else href
        else:
            url = site.get("listing_url", "")

        if not title or title == "(geen titel gevonden)":
            title = card.get_text(" ", strip=True)[:160] or "(geen titel gevonden)"

        item = {
            "id": url or title,
            "title": title,
            "price_text": price_text,
            "price": parse_price(price_text),
            "city": city,
            "url": url,
        }
        items.append(item)
    return items


def passes_filters(item: dict, filters: dict | None) -> bool:
    if not filters:
        return True

    city_filter = filters.get("city")
    if city_filter:
        city_value = str(item.get("city") or item.get("location") or "").lower()
        if city_value and str(city_filter).lower() not in city_value:
            return False

    max_price = filters.get("max_price")
    if max_price is not None and item.get("price") is not None and item["price"] > max_price:
        return False

    min_rooms = filters.get("min_rooms")
    rooms = item.get("rooms")
    if min_rooms is not None and rooms is not None and rooms < min_rooms:
        return False
    return True


def check_site(site: dict, state: dict, config: dict) -> int:
    name = site["name"]
    print(f"[{name}] checking {site['listing_url']}")
    try:
        listings = fetch_listings(site)
    except Exception as exc:
        print(f"[{name}] FOUT bij ophalen: {exc}")
        return 0

    if not listings:
        print(
            f"[{name}] geen listings gevonden — controleer de CSS-selectors in config.yaml "
            f"of de nieuwe pagina-structuur van de site."
        )

    seen_ids = set(state.get(name, []))
    new_count = 0

    for item in listings:
        if item["id"] in seen_ids:
            continue
        seen_ids.add(item["id"])
        if not passes_filters(item, site.get("filters")):
            continue
        new_count += 1
        message = f"{item['title']} — {item['price_text']}"
        print(f"[{name}] NIEUW: {message}")
        notify.send(
            config["notify"].get("channels", ["mac"]),
            config["notify"],
            title=f"Nieuwe woning: {name}",
            message=message,
            url=item["url"],
        )

    state[name] = list(seen_ids)
    return new_count


def run_once(config: dict, only_site: str | None = None) -> None:
    state = load_state()
    for site in config.get("sites", []):
        if not site.get("enabled", True):
            continue
        if only_site and site["name"] != only_site:
            continue
        check_site(site, state, config)
    save_state(state)


def main() -> None:
    parser = argparse.ArgumentParser(description="Volg huuraanbod-sites op nieuwe listings.")
    parser.add_argument("--loop", action="store_true", help="Blijf draaien i.p.v. eenmalig checken")
    parser.add_argument("--site", help="Check alleen deze site (naam uit config.yaml)")
    parser.add_argument("--reset-state", action="store_true", help="Wis de opgeslagen seen-state en stop.")
    args = parser.parse_args()

    if args.reset_state:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
            print("State reset: seen.json verwijderd.")
        else:
            print("State reset: geen seen.json gevonden.")
        return

    try:
        config = load_config()
    except Exception as exc:
        print(f"Fout in config.yaml: {exc}", file=sys.stderr)
        raise SystemExit(1)

    if args.loop:
        interval = config.get("check_interval_minutes", 15) * 60
        print(f"Start loop, elke {interval // 60} minuten...")
        while True:
            run_once(config, args.site)
            time.sleep(interval)
    else:
        run_once(config, args.site)


if __name__ == "__main__":
    main()
