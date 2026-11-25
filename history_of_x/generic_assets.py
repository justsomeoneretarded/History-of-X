"""Bounded, scene-specific museum discovery for subjects without a curated collection.

Only explicit CC0/open-access image rights are accepted. A search hit does not
become an event photograph: object date, medium and depiction context travel
with the asset to the director.
"""
from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path

import requests

from .core import key, read_json, save_json

STOP = {"the", "and", "with", "from", "into", "during", "historical", "history",
        "ancient", "modern", "dramatic", "image", "images", "photo", "photograph",
        "painting", "illustration", "archive", "archival", "portrait", "scene"}


def subject_terms(text):
    return set(re.findall(r"[a-z]{3,}", str(text).casefold())) - STOP


def scene_period(scene):
    label = scene.get("date_label", "")
    years = [int(x) for x in re.findall(r"(?<!\w)(\d{3,4})(?!\w)", label)]
    if years:
        return (min(years), max(years))
    century = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+centur", label, re.I)
    if century:
        n = int(century[1])
        if 1 <= n <= 21:
            return ((n - 1) * 100, n * 100 - 1)
    return None


def normalize_record(provider, raw):
    """Normalize only providers with explicit, independently checked image rights."""
    if not isinstance(raw, dict):
        return None
    if provider == "cleveland":
        if raw.get("share_license_status") != "CC0":
            return None
        picture = (raw.get("images") or {}).get("web") or (raw.get("images") or {}).get("print") or {}
        culture_value = raw.get("culture") or []
        culture = culture_value if isinstance(culture_value, str) else " ".join(str(x) for x in culture_value)
        identifier = raw.get("id")
        image_url = picture.get("url", "")
        source_url = raw.get("url", "")
        title, date = raw.get("title", ""), raw.get("creation_date", "Date not supplied")
        medium = str(raw.get("type", "")) + " " + str(raw.get("technique", ""))
        tags = culture + " " + " ".join(str(raw.get(k, "")) for k in ("title", "title_in_original_language"))
        begin, end = raw.get("creation_date_earliest"), raw.get("creation_date_latest")
        creator = "; ".join(str(x.get("description") or "") for x in (raw.get("creators") or []) if isinstance(x, dict)) or culture
    elif provider == "met":
        if raw.get("isPublicDomain") is not True:
            return None
        identifier = raw.get("objectID")
        image_url = raw.get("primaryImage") or raw.get("primaryImageSmall") or ""
        source_url = raw.get("objectURL", "")
        title, date = raw.get("title", ""), raw.get("objectDate", "Date not supplied")
        culture = str(raw.get("culture", ""))
        medium = str(raw.get("medium", "")) + " " + str(raw.get("objectName", ""))
        tags = culture + " " + title + " " + " ".join(
            x.get("term", "") for x in raw.get("tags") or [] if isinstance(x, dict))
        begin, end = raw.get("objectBeginDate"), raw.get("objectEndDate")
        creator = raw.get("artistDisplayName") or culture
    else:
        return None
    if not identifier or not title or not isinstance(image_url, str) or not isinstance(source_url, str):
        return None
    if not image_url.startswith("https://") or not source_url.startswith("https://"):
        return None
    photographic = bool(re.search(r"photograph|gelatin|albumen|daguerreotype|collodion", medium, re.I))
    return {"id": f"{provider}-{identifier}", "subject": title, "title": title,
            "date": date, "medium": "historical_photo" if photographic else "object_photo",
            "license": "CC0 1.0", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "source_url": source_url, "creator": creator or "Not supplied",
            "provider": "Cleveland Museum of Art Open Access" if provider == "cleveland" else "The Metropolitan Museum of Art Open Access",
            "context": ("Digitized photograph; creation date is supplied, not an assumed event date. "
                        if photographic else "Modern digitization of a collection object or artwork; not live footage of the narrated event. ")
                       + "Collection creation date: " + str(date) + ".",
            "_image_url": image_url, "_match": subject_terms(tags + " " + medium),
            "_begin": begin, "_end": end}


def relevant(record, scene, query):
    terms = subject_terms(query)
    if not terms or len(terms & record["_match"]) < min(2, len(terms)):
        return False
    if record["medium"] == "historical_photo":
        period = scene_period(scene)
        begin, end = record.get("_begin"), record.get("_end")
        # A later photograph cannot silently become contemporaneous event evidence.
        if not period or not isinstance(begin, int) or not isinstance(end, int):
            return False
        if begin > period[1] + 5 or end < period[0] - 5:
            return False
    return True


def discover(script, directory, session=None, max_assets=8):
    from .documentary_assets import USER_AGENT, _download_image
    directory = Path(directory) / "discovered"
    directory.mkdir(parents=True, exist_ok=True)
    session = session or requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    budget, deadline = 36, time.monotonic() + 240
    status, assets, assignments, seen, searches = [], [], {}, set(), set()

    def get_json(url, params=None):
        nonlocal budget
        cache = directory / "metadata" / (key(url, params) + ".json")
        if cache.exists():
            return read_json(cache)
        if budget <= 0 or time.monotonic() > deadline:
            raise TimeoutError("Museum discovery request budget reached")
        budget -= 1
        response = session.get(url, params=params, timeout=(5, 12))
        response.raise_for_status()
        raw = response.json()
        save_json(cache, raw)
        return raw

    for scene in script["scenes"]:
        query = " ".join(str(scene.get("asset_search_term", "")).split())[:140]
        if not query or query in searches:
            continue
        searches.add(query)
        if len(searches) > 10 or len(assets) >= max_assets or time.monotonic() > deadline:
            break
        for provider in ("cleveland", "met"):
            try:
                if provider == "cleveland":
                    data = get_json("https://openaccess-api.clevelandart.org/api/artworks/",
                                    {"q": query, "has_image": 1, "cc0": "", "limit": 4})
                    rows = data.get("data", [])
                else:
                    # The old /v1/search retired in October 2026.
                    data = get_json("https://collectionapi.metmuseum.org/public/collection/v1.1/search",
                                    {"q": query, "hasImages": "true", "offset": 0, "limit": 3})
                    rows = [get_json("https://collectionapi.metmuseum.org/public/collection/v1/objects/" + str(i))
                            for i in (data.get("objectIDs") or [])[:3]]
                found = 0
                for raw in rows if isinstance(rows, list) else []:
                    record = normalize_record(provider, raw)
                    if record is None or not relevant(record, scene, query):
                        continue
                    ident = record["id"]
                    if ident not in seen:
                        target = directory / (ident + ".jpg")
                        _download_image(session, record["_image_url"], target)
                        record["path"] = str(target.resolve())
                        record["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
                        record["tags"] = sorted(subject_terms(query) & record["_match"])
                        assets.append(record)
                        seen.add(ident)
                    assignments.setdefault(str(scene["scene_id"]), []).append(ident)
                    found += 1
                    if found >= 2 or len(assets) >= max_assets:
                        break
                status.append({"provider": provider, "query": query, "accepted": found})
            except (requests.RequestException, ValueError, KeyError, OSError, TimeoutError) as exc:
                status.append({"provider": provider, "query": query, "status": "unavailable",
                               "reason": type(exc).__name__})
            if len(assets) >= max_assets or budget <= 0 or time.monotonic() > deadline:
                break
    # Reuse only specifically matching collection subjects in later scenes.
    for scene in script["scenes"]:
        query = str(scene.get("asset_search_term", ""))
        matches = [a["id"] for a in assets if relevant(a, scene, query)]
        assignments[str(scene["scene_id"])] = list(dict.fromkeys(
            assignments.get(str(scene["scene_id"]), []) + matches))[:3]
    cleaned = [{k: v for k, v in a.items() if not k.startswith("_")} for a in assets]
    return {"assets": cleaned, "scenes": assignments, "provider_status": status}
