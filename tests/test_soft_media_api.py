"""Transport contracts: soft JSON still validates downstream; no paid-model or quota bypass."""
import json
import pytest
import requests
from history_of_x.media_api import MediaAPI
from history_of_x.gemini import QuotaDeferred

class Session:
    def __init__(self):self.bodies=[]
    def post(self,url,**kwargs):
        self.bodies.append(kwargs['json'])
        response=requests.Response();response.status_code=200
        response._content=json.dumps({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"ok":true}'}]}}]}).encode()
        return response

def gateway(tmp_path,monkeypatch):
    monkeypatch.setenv('GEMINI_MEDIA_LEDGER',str(tmp_path/'ledger.json'))
    now=[1000.]
    def sleep(seconds):now[0]+=seconds
    session=Session()
    return MediaAPI(tmp_path/'api',session=session,clock=lambda:now[0],sleeper=sleep),session

def test_soft_mode_moves_bounds_to_prompt_without_mutating_caller(tmp_path,monkeypatch):
    api,session=gateway(tmp_path,monkeypatch);monkeypatch.setenv('GEMINI_SCHEMA_MODE','prompt')
    shape={'type':'object','properties':{'ok':{'type':'string','minLength':6}}}
    body={'contents':[{'role':'user','parts':[{'text':'Return JSON.'}]}],'generationConfig':{'responseJsonSchema':shape}}
    api.request('gemini-3.5-flash-lite','models/test:generateContent',body,'text')
    sent=session.bodies[0]
    assert 'responseJsonSchema' not in sent['generationConfig']
    assert sent['generationConfig']['responseMimeType']=='application/json'
    assert '"minLength": 6' in sent['contents'][0]['parts'][0]['text']
    assert body['generationConfig']['responseJsonSchema']==shape
    assert body['contents'][0]['parts'][0]['text']=='Return JSON.'

def test_model_budgets_do_not_exhaust_another_free_model(tmp_path,monkeypatch):
    api,session=gateway(tmp_path,monkeypatch);monkeypatch.setenv('GEMINI_TEXT_REQUEST_BUDGET','1')
    body={'contents':[{'role':'user','parts':[{'text':'First request'}]}],'generationConfig':{}}
    api.request('gemini-3.5-flash-lite','models/test:generateContent',body,'text')
    api.request('gemini-3.8-flash','models/test:generateContent',body,'text')
    with pytest.raises(QuotaDeferred):
        api.request('gemini-3.8-flash','models/test:generateContent',{**body,'extra':'uncached'},'text')
    assert len(session.bodies)==2

def test_schema_modes_use_distinct_response_cache_entries(tmp_path,monkeypatch):
    api,session=gateway(tmp_path,monkeypatch)
    body={'contents':[{'role':'user','parts':[{'text':'Return JSON.'}]}],'generationConfig':{'responseJsonSchema':{'type':'object'}}}
    monkeypatch.setenv('GEMINI_SCHEMA_MODE','native')
    api.request('gemini-3.5-flash-lite','models/test:generateContent',body,'text')
    monkeypatch.setenv('GEMINI_SCHEMA_MODE','prompt')
    api.request('gemini-3.5-flash-lite','models/test:generateContent',body,'text')
    api.request('gemini-3.5-flash-lite','models/test:generateContent',body,'text')
    assert len(session.bodies)==2
