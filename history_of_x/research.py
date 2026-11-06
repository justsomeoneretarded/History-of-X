"""Evidence discovery from Wikipedia with explicit provenance, not invented citations."""
from __future__ import annotations
import re
import requests
from .core import PipelineError, save_json

SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'HistoryOfX/0.1 (documentary research; github.com/justsomeoneretarded/History-of-X)'

def get(url, **kwargs):
    response = SESSION.get(url, timeout=(15, 50), **kwargs)
    response.raise_for_status()
    return response

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
    if re.search(r'ethiopi', title+' '+brief, re.I):
        names = ['History of Ethiopia', 'Kingdom of Aksum', 'Battle of Adwa', 'Italian occupation of Ethiopia', 'Derg', 'Ethiopian Civil War']
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
