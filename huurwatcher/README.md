# huurwatcher

Checkt periodiek huuraanbod-sites (Vesteda, MVGM, VBT, of elke andere site
met een HTML-resultatenpagina) op nieuwe listings die aan jouw criteria
voldoen, en stuurt een macOS-notificatie (en/of Telegram-bericht) zodra er
iets nieuws staat.

Het reageert niet automatisch namens jou — het waarschuwt je zo snel
mogelijk zodat jij zelf (met een persoonlijk bericht) kunt reageren. Dat is
vrijwel altijd effectiever dan een generiek auto-bericht, en voorkomt dat je
tegen anti-bot maatregelen aanloopt.

## 1. Installatie (macOS, terminal)

```bash
cd huurwatcher
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Config invullen: `config.yaml`

Voor elke site staat er een blok met:
- `listing_url`: de URL van de resultatenpagina, mét jouw filters
  (stad/prijs/kamers) erin. Makkelijkste manier: ga naar de site, stel de
  filters handmatig in, en kopieer de URL uit de adresbalk.
- vier CSS-selectors (`listing_selector`, `title_selector`,
  `price_selector`, `link_selector`) — dit zijn placeholders die je zelf
  invult, zie stap 3.
- `filters.max_price` (en eventueel meer, zie hieronder).

Zet een site op `enabled: true` om hem mee te laten draaien.

## 3. Selectors vinden met Chrome/Safari devtools

Dit is de enige handmatige stap per site, en hoeft maar één keer (tenzij de
site zijn layout verandert):

1. Open de resultatenpagina in Chrome.
2. Rechtsklik op één losse woning-kaart in de lijst → **Inspecteren**.
3. Je ziet nu een HTML-element gemarkeerd, meestal iets als
   `<div class="property-card">...</div>` — de class-naam
   (`property-card`) is je `listing_selector`, geschreven als
   `.property-card`.
4. Klap dat element open en zoek binnenin het element met de titel
   (bijv. `<h3 class="property-card__title">Herengracht 123</h3>`) →
   dat wordt je `title_selector`: `.property-card__title`.
5. Zelfde voor de prijs.
6. Voor de link: meestal is de hele kaart of de titel een `<a href="...">`
   — dan is `link_selector: "a"` genoeg.

Tip: rechtsklik op het element in de Elements-tab → **Copy → Copy
selector** geeft een (soms wat lang) werkend selector-pad — prima als je
zelf niet de "nette" class wil uitzoeken.

## 4. Testen

```bash
python scraper.py --site vesteda
```

Als je "geen listings gevonden" ziet, klopt een van de selectors nog niet
— check met devtools of de class-namen nog overeenkomen (sommige sites
laden de lijst pas na een JavaScript-call; zie "Als de site JS-rendered
is" hieronder).

## 5. Notificaties

**macOS (standaard, werkt direct):** gebruikt `osascript` om een native
macOS-notificatie te tonen. Geen setup nodig.

**Telegram (optioneel, handig als je niet achter je Mac zit):**
1. Stuur `/newbot` naar [@BotFather](https://t.me/BotFather) in Telegram,
   volg de stappen, je krijgt een `bot_token`.
2. Stuur een willekeurig bericht naar je nieuwe bot.
3. Ga naar `https://api.telegram.org/bot<JOUW_TOKEN>/getUpdates` in je
   browser, zoek `"chat":{"id":...}` — dat getal is je `chat_id`.
4. Vul beide in bij `notify.telegram` in `config.yaml`, en zet
   `channels: ["mac", "telegram"]`.

## 6. Automatisch laten draaien: cron

```bash
crontab -e
```

Voeg toe (checkt elke 5 minuten, pas het pad aan naar waar je de map hebt
staan):

```
*/5 * * * * cd /Users/JOUWNAAM/huurwatcher && .venv/bin/python scraper.py >> run.log 2>&1
```

Let op: je Mac moet aan/wakker zijn op de momenten dat cron draait —
`caffeinate` of "voorkom in slaap" in Energiebeheer kan helpen als je hem
laat draaien terwijl je weg bent. Alternatief: laat 'm draaien met
`python scraper.py --loop` in een Terminal-tabje dat je open laat staan.

## Als een site JavaScript-rendered is

Sommige sites (vooral MVGM en VBT gebruiken soms een losse
zoek-widget/iframe) laden de listings pas na een JS/AJAX-call in plaats
van ze direct in de HTML te zetten. Check dat zo:

1. Devtools → tab **Network** → filter op **Fetch/XHR** → herlaad de
   pagina.
2. Zoek een request dat JSON teruggeeft met de woninggegevens erin (vaak
   iets als `.../api/listings?city=amsterdam`).
3. Als je die vindt: dat is veel prettiger dan HTML-scrapen — laat het
   weten, dan bouw ik een variant die die JSON-endpoint direct aanroept
   in plaats van CSS-selectors te gebruiken (sneller en stabieler).
4. Als je zo'n endpoint niet kan vinden en de pagina echt pas na
   JavaScript vult, heb je Selenium/Playwright nodig i.p.v. `requests` —
   laat het ook weten, dan breid ik het script daarvoor uit.

## Juridisch/technisch, kort

- Check de `robots.txt` van elke site (bijv. `vesteda.com/robots.txt`) en
  de gebruiksvoorwaarden — sommige sites verbieden scraping expliciet.
  Dit script is bedoeld voor persoonlijk, laagfrequent gebruik (elke
  15+ minuten), niet voor agressief pollen.
- Zet `check_interval_minutes` niet te laag; elke 10-15 minuten is meer
  dan snel genoeg om als eerste te reageren, en voorkomt dat je IP als
  bot-verkeer wordt gezien.
