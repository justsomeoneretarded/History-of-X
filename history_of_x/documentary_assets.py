"""Licensed, subject-specific documentary media; provenance stays outside the frame.

This catalogue deliberately separates a present-day photograph of an ancient
building, a later painting of a battle, and contemporaneous footage. A matching
country name is never sufficient to put an asset into a historical scene.
"""
from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

import requests
from PIL import Image

from .core import ROOT, read_json, save_json

TIMEOUT = (10, 25)
MAX_IMAGE_BYTES = 12 * 1024 * 1024
USER_AGENT = "HistoryOfX/1.0 (documentary open-access media; provenance retained)"

# Editorial subject rules for the existing, licensed Ethiopia collection. These
# are not searches: every file is already identified by a manifest with credits.
_RULES = [
    ("battle of adwa", ["adwa", "adoua"], "historical_artwork", "Depicts the Battle of Adwa (1896); painting date not supplied", "A historical representation of Adwa, not a photograph of the battle."),
    ("main stelae field", ["aksum", "axum", "stela", "obelisk"], "modern_documentary_photo", "Modern photograph of ancient Aksumite remains", "Use as surviving material evidence, never as ancient live footage."),
    ("axum. ezanas", ["ezana", "aksum", "axum", "coin"], "object_photo", "Aksumite coin, c. 330–360; modern object photograph", "Ancient coin photographed in modern times."),
    ("axumite coinage", ["aksum", "axum", "coin", "trade"], "object_photo", "Ancient Aksumite coin; modern object photograph", "British Museum object photograph."),
    ("bete giyorgis", ["lalibela", "rock-hewn", "rock hewn"], "modern_documentary_photo", "Modern photograph of the medieval church at Lalibela", "The surviving church; not footage of medieval construction."),
    ("menelik", ["menelik"], "historical_photo", "Late nineteenth/early twentieth century; exact photograph date unconfirmed", "Identified portrait of Menelik II. Do not substitute for another emperor."),
    ("taytu betul", ["taytu", "taitu"], "historical_photo", "Late nineteenth/early twentieth century; exact photograph date unconfirmed", "Identified portrait of Taytu Betul."),
    ("baratieri", ["baratieri"], "historical_photo", "Nineteenth century; exact photograph date unconfirmed", "Identified portrait of Oreste Baratieri."),
    ("mustard gas", ["mustard gas", "chemical", "1935", "1936", "second italo"], "historical_photo", "Second Italo-Ethiopian War (1935–1936)", "Never use as the First Italo-Ethiopian War or the 1896 battle."),
    ("swedish-red-cross", ["red cross", "1935", "1936", "second italo"], "historical_photo", "Second Italo-Ethiopian War (1935–1936)", "Red Cross facility during the second invasion; inspect for distressing content before use."),
    ("wolchefit", ["1941", "wolchefit", "liberation", "restored", "restoration"], "historical_photo", "28 September 1941", "King's African Rifles collecting surrendered arms. Not Ethiopian troops at Adwa."),
    ("gebrehiwot meshesha", ["arben", "arbegnoch", "resistance", "occupation", "1936", "1941"], "historical_photo", "Italian occupation/resistance period (1936–1941); exact image date unconfirmed", "Identified Ethiopian resistance commander Gebrehiwot Meshesha."),
    ("haile selassie", ["haile selassie", "selassie"], "historical_photo", "Twentieth century; exact portrait date unconfirmed", "Identified portrait of Haile Selassie I."),
    ("mengistu", ["mengistu", "derg"], "historical_photo", "Derg era (1974–1991); exact image date unconfirmed", "Identified Mengistu Haile Mariam portrait/propaganda image."),
    ("horn of africa", ["horn of africa", "red sea", "geography"], "satellite_image", "31 December 2021", "Modern NASA satellite geography, never a historical border map."),
    ("simien mountains", ["simien", "highlands", "terrain"], "modern_documentary_photo", "Modern photograph; acquisition date not confirmed", "Physical landscape only; does not establish historical troop locations."),
    ("tigray", ["tigray", "tigrayan"], "modern_documentary_photo", "Modern photograph; acquisition date not confirmed", "Landscape/context only; never presented as footage of a war or famine."),
    ("danakil", ["danakil", "depression"], "modern_documentary_photo", "2019", "Modern geographic context; not historical event evidence."),
]


def _tokens(text):
    return re.sub(r"[^\w\s-]", " ", text.casefold())


def _mentions(text, phrase):
    return bool(re.search(r"(?<!\w)" + re.escape(phrase.casefold()) + r"(?!\w)", _tokens(text)))


def matching_assets(scene, assets, limit=8):
    """Return candidates by explicit subject, never by country-name similarity.

    The director still chooses whether a candidate contributes to a particular
    shot. Candidate availability is not an instruction to decorate the frame.
    """
    text = " ".join(str(scene.get(k, "")) for k in ("narration", "asset_search_term", "location"))
    matches = []
    for asset in assets:
        hits = [tag for tag in asset.get("tags", []) if _mentions(text, tag)]
        if not hits:
            continue
        # The 1935 archive is especially easy to misapply to the 1896 campaign.
        if asset["medium"] == "archival_video" and not any(_mentions(text, tag) for tag in asset.get("required_context", [])):
            continue
        specificity = max(len(tag.split()) * 10 + len(tag) for tag in hits)
        if asset["medium"] == "modern_documentary_photo":
            specificity -= 8
        matches.append((specificity, asset["id"]))
    return [identifier for _, identifier in sorted(matches, key=lambda item: (-item[0], item[1]))[:limit]]


def bundled_assets():
    """Normalize existing licensed records without losing attribution metadata."""
    result = []
    seen = set()
    manifest = ROOT / "assets/presets/ethiopia/manifest.json"
    for raw in read_json(manifest) if manifest.exists() else []:
        title = raw["title"].casefold().replace("_", " ")
        rule = next((row for row in _RULES if row[0] in title), None)
        if not rule or not (ROOT / raw["bundled_path"]).exists():
            continue
        # Recent commissioned paintings need separate rights/context and are
        # unnecessary when archival portraits and identified historical art exist.
        if "tewodros abebaw" in title:
            continue
        digest = raw.get("sha256", raw["bundled_path"])
        if digest in seen:
            continue
        seen.add(digest)
        _, tags, medium, date, context = rule
        # Several portraits in the legacy collection are newspaper engravings,
        # not photographs. Preserve that distinction for editorial decisions.
        description = raw.get("description", "").casefold()
        if "newspaper" in description or "xilografia" in description:
            medium = "historical_artwork"
            date = "Late nineteenth-century newspaper illustration; exact publication date unconfirmed"
            context = "Historical newspaper illustration, not a photograph. " + context
        result.append({
            "id": "ethiopia-" + Path(raw["bundled_path"]).stem,
            "path": str(ROOT / raw["bundled_path"]),
            "subject": raw["title"].removeprefix("File:"),
            "title": raw["title"].removeprefix("File:"),
            "date": date, "medium": medium, "context": context,
            "tags": tags, "license": raw["license"],
            "license_url": raw.get("license_url", ""),
            "source_url": raw["source_url"],
            "creator": raw.get("artist", "Unknown"),
            "provider": "Wikimedia Commons licensed collection",
            "sha256": raw.get("sha256", ""),
        })
    for raw in read_json(ROOT / "assets/footage/catalog.json"):
        path = ROOT / raw["path"]
        if path.exists():
            result.append({**raw, "path": str(path), "subject": raw["title"],
                           "medium": "archival_video", "provider": "Internet Archive / Universal Newsreel",
                           "tags": ["haile selassie", "1935", "second italo", "italian invasion"],
                           "required_context": ["1935", "second italo", "italian invasion", "mussolini"]})
    return result


def _download_image(session, url, target):
    """One bounded transfer, decoded before acceptance; no HTML masquerading as art."""
    if target.exists():
        with Image.open(target) as image:
            image.verify()
        return target
    response = session.get(url, timeout=TIMEOUT, stream=True)
    response.raise_for_status()
    if int(response.headers.get("Content-Length", 0)) > MAX_IMAGE_BYTES:
        raise ValueError("Museum image exceeds bounded download size")
    data = bytearray()
    for block in response.iter_content(65536):
        data.extend(block)
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError("Museum image exceeds bounded download size")
    with Image.open(io.BytesIO(data)) as image:
        if image.width < 300 or image.height < 300:
            raise ValueError("Museum image is too small")
        image = image.convert("RGB")
        image.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, quality=94)
    return target


def museum_assets(directory, session=None):
    """Fetch two curated CC0 Ethiopian works from the Cleveland open-access API.

    Curated object IDs avoid the frequent search error where the word Ethiopia
    occurs in an unrelated object's bibliography. Metadata must independently
    identify Ethiopian culture and CC0 rights before the image is accepted.
    """
    session = session or requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    assets, status = [], []
    selections = [
        (160940, ["church", "christian", "christianity", "manuscript", "gospel", "religious"],
         "Medieval Ethiopian manuscript; material evidence of religious art, not a portrait of an emperor."),
        (535124, ["gondar", "gondär", "fasilides", "religious art", "apostles"],
         "Ethiopian diptych c.1700, attributed to Gondar; material evidence of the period's art."),
    ]
    for identifier, tags, context in selections:
        cache = Path(directory) / "museum" / f"cleveland-{identifier}.json"
        try:
            if cache.exists():
                raw = read_json(cache)
            else:
                response = session.get(f"https://openaccess-api.clevelandart.org/api/artworks/{identifier}", timeout=TIMEOUT)
                response.raise_for_status()
                raw = response.json()["data"]
                if isinstance(raw, list):
                    raw = raw[0]
            culture = " ".join(raw.get("culture", []))
            if "ethiopia" not in culture.casefold() or raw.get("share_license_status") != "CC0":
                raise ValueError("Museum attribution/CC0 rights did not match curated object")
            image = raw["images"].get("print") or raw["images"]["web"]
            target = Path(directory) / "museum" / f"cleveland-{identifier}.jpg"
            _download_image(session, image["url"], target)
            save_json(cache, raw)
            assets.append({"id": f"cleveland-{identifier}", "path": str(target.resolve()),
                           "subject": raw["title"], "title": raw["title"],
                           "date": raw.get("creation_date", "Date not supplied"),
                           "license": "CC0 1.0", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                           "source_url": raw["url"], "creator": culture,
                           "provider": "Cleveland Museum of Art Open Access", "medium": "object_photo",
                           "context": context, "tags": tags,
                           "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
            status.append({"provider": "Cleveland Museum of Art", "object": identifier, "status": "available"})
        except (requests.RequestException, ValueError, KeyError, OSError) as error:
            # Absence is visible and never silently replaced with unrelated art.
            status.append({"provider": "Cleveland Museum of Art", "object": identifier,
                           "status": "unavailable", "reason": type(error).__name__})
    # The Met's newer search API is paginated, but this identified processional
    # cross can be fetched directly. Many search hits for 'Ethiopia' have no
    # open image or are actually Japanese/European objects: do not accept those.
    identifier = 677838
    cache = Path(directory) / "museum" / f"met-{identifier}.json"
    try:
        if cache.exists():
            raw = read_json(cache)
        else:
            response = session.get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{identifier}", timeout=TIMEOUT)
            response.raise_for_status()
            raw = response.json()
        if not raw.get("isPublicDomain") or "ethiopia" not in raw.get("culture", "").casefold():
            raise ValueError("Met Ethiopian attribution/public-domain rights not established")
        target = Path(directory) / "museum" / f"met-{identifier}.jpg"
        _download_image(session, raw.get("primaryImage") or raw["primaryImageSmall"], target)
        save_json(cache, raw)
        assets.append({"id": f"met-{identifier}", "path": str(target.resolve()),
                       "subject": raw["title"], "title": raw["title"],
                       "date": raw["objectDate"], "license": "CC0 1.0",
                       "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                       "source_url": raw["objectURL"], "creator": raw["culture"],
                       "provider": "The Metropolitan Museum of Art Open Access", "medium": "object_photo",
                       "context": "Early fifteenth-century Ethiopian processional cross from Lasta; surviving religious artifact, not a photograph of medieval ceremony.",
                       "tags": ["christian", "christianity", "cross", "church", "lasta", "religious"],
                       "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
        status.append({"provider": "The Metropolitan Museum of Art", "object": identifier, "status": "available"})
    except (requests.RequestException, ValueError, KeyError, OSError) as error:
        status.append({"provider": "The Metropolitan Museum of Art", "object": identifier,
                       "status": "unavailable", "reason": type(error).__name__})
    return assets, status


def catalog(script, directory, fetch=True, session=None):
    """Build a portable, provenance-rich catalogue and per-scene candidate IDs.

    Returns {assets: [...], scenes: {scene_id: [asset_id]}, provider_status: [...]}.
    Only an Ethiopia film receives the Ethiopia-specific curated collection.
    Other subjects get an explicit empty catalogue rather than Ethiopian filler.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    subject = script.get("title", "") + " " + script.get("summary", "")
    assets, status = [], []
    if _mentions(subject, "ethiopia") or _mentions(subject, "ethiopian") or _mentions(subject, "abyssinia"):
        assets = bundled_assets()
        status.append({"provider": "Curated licensed collection / Internet Archive", "status": "available", "count": len(assets)})
        if fetch:
            extra, museum_status = museum_assets(directory, session)
            assets.extend(extra)
            status.extend(museum_status)
    else:
        status.append({"provider": "Curated collection", "status": "no_subject_collection", "count": 0})
    result = {"assets": assets,
              "scenes": {str(scene["scene_id"]): matching_assets(scene, assets) for scene in script["scenes"]},
              "provider_status": status}
    save_json(directory / "documentary-assets.json", result)
    return result
