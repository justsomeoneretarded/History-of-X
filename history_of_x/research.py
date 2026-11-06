"""Evidence discovery from Wikipedia with explicit provenance, not invented citations."""
from __future__ import annotations
import re
import time
from urllib.parse import urlparse
import requests
from .core import PipelineError, save_json

SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'HistoryOfX/0.1 (documentary research; github.com/justsomeoneretarded/History-of-X)'

_LAST_REQUEST={}

def get(url, **kwargs):
    host=urlparse(url).hostname or ''
    paced=host.endswith('wikimedia.org') or host.endswith('wikipedia.org')
    for attempt in range(5):
        if paced:
            wait=max(0,_LAST_REQUEST.get(host,0)+1.2-time.monotonic())
            if wait:time.sleep(wait)
            _LAST_REQUEST[host]=time.monotonic()
        try:
            response=SESSION.get(url,timeout=(15,50),**kwargs)
        except (requests.Timeout,requests.ConnectionError):
            if attempt==4:raise
            time.sleep(5*2**attempt)
            continue
        if response.status_code not in (429,500,502,503,504):
            response.raise_for_status()
            return response
        if attempt==4:
            response.raise_for_status()
        delay=5*2**attempt
        retry=response.headers.get('Retry-After','')
        if retry:
            try:delay=max(delay,float(retry))
            except ValueError:
                from email.utils import parsedate_to_datetime
                from datetime import datetime,timezone
                try:delay=max(delay,(parsedate_to_datetime(retry)-datetime.now(timezone.utc)).total_seconds())
                except (ValueError,TypeError):pass
        response.close()
        if delay>120:
            raise PipelineError(f'{host} requested a long cooldown. Accepted work is saved; resume after the service recovers.')
        print(f'{host}: HTTP {response.status_code}; waiting {delay:.0f}s before bounded retry {attempt+1}/4.',flush=True)
        time.sleep(delay)
    raise PipelineError(f'{host} is unavailable after bounded retries')

def wiki(params):
    data = get('https://en.wikipedia.org/w/api.php', params={'format': 'json', 'formatversion': 2, 'redirects': 1, **params}).json()
    if 'error' in data:
        raise PipelineError('Wikipedia API returned an error')
    return data

def research(title, brief, directory):
    from .core import read_json, key
    output = directory / 'research.json'
    fingerprint = key('research-v1', title, brief)
    if output.exists() and read_json(output).get('fingerprint') == fingerprint:
        return read_json(output)
    query = title if len(title.split()) < 10 else ' '.join(title.split()[:8])
    hits = wiki({'action':'query', 'list':'search', 'srsearch':query, 'srlimit':5})['query']['search']
    if not hits:
        raise PipelineError('No research sources found. Supply a more specific title or an evidence file.')
    names = [h['title'] for h in hits]
    if re.search(r'^(?:the\s+)?(?:entire\s+)?(?:history\s+of\s+)?ethiopia(?:\s*[:—-]|$)', title, re.I):
        names = ['History of Ethiopia', 'Kingdom of Aksum', 'Battle of Adwa', 'Italian occupation of Ethiopia', 'Derg', 'Ethiopian Civil War']
    for entity in focus_topics(brief):
        matches=wiki({'action':'query','list':'search','srsearch':f'intitle:"{entity}" {title}','srlimit':1})['query']['search']
        if matches and matches[0]['title'] not in names:names.append(matches[0]['title'])
    names=list(dict.fromkeys(names))[:8]
    sources = []
    for index, name in enumerate(names):
        pages = wiki({'action':'query','prop':'extracts|info','inprop':'url','explaintext':1,'titles':name})['query']['pages']
        for page in pages:
            if not page.get('extract'):
                continue
            sources.append({'id':f'S{index+1}', 'title':page['title'], 'url':page['fullurl'],
                            'extract':page['extract'][:7000], 'source_kind':'reference overview; follow its cited works for deeper verification'})
    if not sources:
        raise PipelineError('Sources did not contain usable evidence')
    result = {'fingerprint':fingerprint, 'title':title, 'brief':brief, 'sources':sources,
              'limitations':'Automated evidence extraction is not a substitute for a historian. Interpretations and disputed estimates require review.'}
    save_json(output, result)
    return result


def focus_topics(brief):
    match=re.search(r'(?:focus on|include|cover)\s+([^.]+)',brief,re.I)
    if not match:return []
    names=re.findall(r'\b[A-Z][a-z]+(?:\s+(?:[A-Z][a-z]+|[IVX]{1,4}))*\b',match.group(1))
    adjectives={'Italian','Ethiopian','British','French','European','African','American','Russian','Chinese','German'}
    return [name for name in dict.fromkeys(names) if name not in adjectives][:2]
