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


def test_gemma_uses_plain_text_schema_and_supported_generation_controls(tmp_path,monkeypatch):
    api,session=gateway(tmp_path,monkeypatch)
    monkeypatch.setenv('GEMINI_SCHEMA_MODE','native')
    shape={'type':'object','required':['ok'],'properties':{'ok':{'type':'boolean'}}}
    assert api.text('Return JSON.',{},shape,model='gemma-4-26b-a4b-it')=={'ok':True}
    sent=session.bodies[0]
    assert 'responseJsonSchema' not in sent['generationConfig']
    assert 'responseMimeType' not in sent['generationConfig']
    assert sent['generationConfig']['thinkingConfig']=={'thinkingLevel':'MINIMAL'}
    assert '"required": ["ok"]' in sent['contents'][0]['parts'][0]['text']

def test_plain_text_gemma_accepts_only_a_complete_json_fence():
    from history_of_x.media_api import json_text
    fence=chr(96)*3
    assert json_text(fence+'json\n{"ok":true}\n'+fence,'gemma-4-31b-it')=='{"ok":true}'
    assert json_text('Here is some text {"ok":true}','gemma-4-31b-it').startswith('Here is')

def test_gemma_invalid_json_is_not_saved_as_an_accepted_response(tmp_path,monkeypatch):
    from history_of_x.core import PipelineError
    class InvalidSession(Session):
        def post(self,url,**kwargs):
            response=super().post(url,**kwargs)
            response._content=json.dumps({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'not JSON'}]}}]}).encode()
            return response
    monkeypatch.setenv('GEMINI_MEDIA_LEDGER',str(tmp_path/'ledger.json'))
    api=MediaAPI(tmp_path/'api',session=InvalidSession())
    with pytest.raises(PipelineError,match='not cached'):
        api.text('Return JSON.',{}, {'type':'object'},model='gemma-4-26b-a4b-it')
    assert not list((tmp_path/'api').glob('*.json'))

def test_gemma_is_not_used_for_video_or_image_review(tmp_path,monkeypatch):
    from history_of_x.core import PipelineError
    api,session=gateway(tmp_path,monkeypatch)
    body={'contents':[{'parts':[{'inlineData':{'mimeType':'video/mp4','data':'AA=='}}]}],'generationConfig':{}}
    with pytest.raises(PipelineError,match='text-only'):
        api.request('gemma-4-31b-it','models/test:generateContent',body,'text')
    assert session.bodies==[]


def test_incomplete_output_retains_finish_and_usage_without_thought_content(tmp_path,monkeypatch):
    from history_of_x.core import PipelineError
    class Incomplete(Session):
        def post(self,url,**kwargs):
            response=super().post(url,**kwargs)
            response._content=json.dumps({
             'candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':[
              {'thought':True,'text':'private intermediate reasoning'},
              {'text':'{"nodes":['}]}}],
             'usageMetadata':{'thoughtsTokenCount':3400}}).encode()
            return response
    monkeypatch.setenv('GEMINI_MEDIA_LEDGER',str(tmp_path/'ledger.json'))
    api=MediaAPI(tmp_path/'api',session=Incomplete())
    with pytest.raises(PipelineError,match='finishReason=MAX_TOKENS'):
        api.text('Return JSON.',{}, {'type':'object'},max_output=3500,model='gemma-4-26b-a4b-it')
    assert not list((tmp_path/'api').glob('*.json'))
    diagnostic=json.loads(next((tmp_path/'api/diagnostics').glob('*.json')).read_text())
    assert diagnostic['requested_max_output']==3500
    assert diagnostic['response']['usageMetadata']['thoughtsTokenCount']==3400
    assert 'private intermediate' not in json.dumps(diagnostic)
