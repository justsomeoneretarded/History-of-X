import json
from pathlib import Path
import pytest
from PIL import Image,ImageChops
from history_of_x.core import PipelineError,duration,probe
from history_of_x.media_api import MediaAPI
from history_of_x.explainer_plan import timing_beats
from history_of_x.vector_art import icon,ICONS
from history_of_x.animated_render import shot_video,captions
from history_of_x.explainer_package import draw_thumbnail

def sample():
 return {'beat_id':'1-1','global_start':0,'global_end':3,'headline':'TWO TRANSLATIONS','year_label':'1889','year':1889,'background':'cream','action':'clash','nodes':[{'icon':'ruler','label':'Menelik II','color':'teal'},{'icon':'broken_document','label':'The treaty','color':'coral'}],'text':'Two translations became a diplomatic trap.','sting':False,'rationale':'Treaty dispute'}

def test_all_original_icons_render():
 for kind in ICONS:
  im=icon(kind,size=200)
  assert im.size==(200,200) and im.getbbox()

def test_timing_beats_preserve_words_and_rhythm():
 words=[{'word':str(i),'start':i*.3,'end':i*.3+.25} for i in range(120)]
 beats=timing_beats(words,36,1)
 assert all(3<=b['end']-b['start']<=6 for b in beats)
 assert ' '.join(b['text'] for b in beats)==' '.join(str(i) for i in range(120))
 assert beats[0]['start']==0 and beats[-1]['end']==36

def test_clean_caption_track(tmp_path):
 script={'scenes':[{'subtitle_highlights':['treaty']}]};speech={'scenes':[{'duration':3,'captions':[{'start':0,'end':3,'text':'The treaty failed.'}]}]}
 captions(tmp_path,script,speech,960,540)
 text=(tmp_path/'captions.ass').read_text()
 assert 'HISTORY OF X' not in text and 'Dialogue: 1' not in text
 assert 'treaty' in (tmp_path/'captions.srt').read_text()

def test_thumbnail_upload_dimensions(tmp_path):
 path=tmp_path/'thumbnail.jpg';draw_thumbnail({'text':'ITALY MISCALCULATED','background':'navy','nodes':[{'icon':'ruler','color':'teal'},{'icon':'cannon','color':'gold'}]},path)
 assert Image.open(path).size==(1280,720) and path.stat().st_size<2_000_000

class Response:
 ok=True;status_code=200
 def json(self):return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"ok":true}'}]}}]}
class Session:
 def __init__(self):self.calls=0
 def post(self,*a,**kw):self.calls+=1;return Response()

def test_media_api_pacing_caching_and_budget(tmp_path,monkeypatch):
 monkeypatch.delenv('GEMINI_MEDIA_LEDGER',raising=False);monkeypatch.setenv('GEMINI_TEXT_REQUEST_BUDGET','2')
 now=[1000.];waits=[]
 def wait(s):waits.append(s);now[0]+=s
 client=Session();api=MediaAPI(tmp_path,client,lambda:now[0],wait)
 schema={'type':'object','properties':{'ok':{'type':'boolean'}}}
 assert api.text('one',{},schema)=={'ok':True}
 api.text('one',{},schema);assert client.calls==1
 api.text('two',{},schema);assert client.calls==2 and sum(waits)>=65 and max(waits)<=45
 from history_of_x.gemini import QuotaDeferred
 with pytest.raises(QuotaDeferred):api.text('three',{},schema)
 with pytest.raises(PipelineError):api.request('unknown-paid','x',{},'text')

def test_real_vector_motion_is_decodable_and_resumable(tmp_path):
 shot=sample();out=shot_video(shot,tmp_path,'draft',0,3)
 assert abs(duration(out)-3)<.1
 stream=probe(out)['streams'][0];assert stream['width']==960 and stream['pix_fmt']=='yuv420p'
 modified=out.stat().st_mtime_ns;assert shot_video(shot,tmp_path,'draft',0,3).stat().st_mtime_ns==modified
