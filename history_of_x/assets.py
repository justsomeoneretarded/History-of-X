"""Licensed Commons visuals; all usage recorded, unknown licensing rejected."""
from __future__ import annotations
import html
import io
import re
import time
from pathlib import Path
from PIL import Image, ImageOps
from .core import PipelineError, key, save_json, read_json
from .research import get

ALLOWED = ('public domain','cc0','cc by-sa','cc-by-sa','cc by','cc-by')

def plain(value):
    return re.sub('<[^>]+>', '', html.unescape(value or '')).strip()

def allowed_license(name):
    name = name.lower().strip()
    return any(name.startswith(x) for x in ALLOWED) and not any(x in name for x in ('nc','nd','noncommercial','no derivatives'))

def discover(query, limit=8):
    data = get('https://commons.wikimedia.org/w/api.php', params={
        'action':'query','format':'json','formatversion':2,'generator':'search',
        'gsrsearch':query+' filetype:bitmap','gsrnamespace':6,'gsrlimit':limit,
        'prop':'imageinfo','iiprop':'url|size|extmetadata','iiurlwidth':1920}).json()
    result = []
    for page in data.get('query', {}).get('pages', []):
        info = (page.get('imageinfo') or [{}])[0]
        meta = info.get('extmetadata', {})
        license_name = plain(meta.get('LicenseShortName',{}).get('value',''))
        if not allowed_license(license_name) or info.get('width',0)<900 or info.get('height',0)<500:
            continue
        result.append({'title':page['title'], 'url':info.get('thumburl') or info['url'],
            'source_url':info['descriptionurl'], 'license':license_name,
            'license_url':meta.get('LicenseUrl',{}).get('value',''), 'artist':plain(meta.get('Artist',{}).get('value','')),
            'description':plain(meta.get('ImageDescription',{}).get('value',''))[:500],
            'width':info['width'], 'height':info['height']})
    return result

def download_asset(record, cache):
    path = cache / (key(record['url'])+'.jpg')
    if path.exists():
        with Image.open(path) as im:
            im.verify()
        return path
    response = get(record['url'], stream=True)
    if int(response.headers.get('content-length','0')) > 30_000_000:
        raise PipelineError('Asset too large')
    data = bytearray()
    for chunk in response.iter_content(65536):
        data.extend(chunk)
        if len(data)>30_000_000:
            raise PipelineError('Asset download exceeded 30 MB')
    with Image.open(io.BytesIO(data)) as im:
        if im.width*im.height > 80_000_000:
            raise PipelineError('Asset pixel limit exceeded')
        im = ImageOps.exif_transpose(im).convert('RGB')
        im.thumbnail((2400,2400))
        im.save(path, quality=94)
    return path

def prepare(script, directory, min_assets=3):
    cache = directory / 'assets'
    cache.mkdir(parents=True, exist_ok=True)
    index = cache / 'index.json'
    manifest = read_json(index) if index.exists() else {}
    used = set()
    for scene in script['scenes']:
        sid = str(scene['scene_id'])
        query = scene['asset_search_term']
        if sid in manifest and manifest[sid].get('query') == query and manifest[sid].get('assets') and all((directory / x['path']).exists() for x in manifest[sid]['assets']):
            used.update(x['source_url'] for x in manifest[sid]['assets'])
            continue
        records = []
        queries = [query, re.sub(r'\b(historical|painting|photograph|artwork|cinematic)\b','',query,flags=re.I).strip()]
        if len(query.split())>=3:
            queries.append(' '.join(query.split()[:-1]))
        for search in dict.fromkeys(queries):
            try:
                candidates = discover(search)
                candidates.sort(key=lambda x: (x['source_url'] in used, abs(x['width']/x['height']-16/9)))
                for record in candidates:
                    if record['source_url'] in {r['source_url'] for r in records}:
                        continue
                    try:
                        path = download_asset(record, cache)
                    except Exception:
                        continue
                    records.append({**record, 'path':str(path.relative_to(directory)), 'modifications':'Cropped, graded, animated camera movement; attribution retained.'})
                    used.add(record['source_url'])
                    if len(records)>=2:
                        break
            except Exception as e:
                print(f'Asset discovery unavailable for scene {sid} ({type(e).__name__})',flush=True)
            if records:
                break
        manifest[sid] = {'query':query,'assets':records}
        save_json(index, manifest)
    count = len({x['source_url'] for entry in manifest.values() for x in entry['assets']})
    save_json(cache/'quality.json', {'unique_assets':count,'minimum':min_assets,'missing_scenes':[k for k,v in manifest.items() if not v['assets']]})
    if count < min_assets:
        raise PipelineError(f'Only {count} licensed assets found; {min_assets} required. Resume after checking asset access; no silent all-placeholder video.')
    return manifest
