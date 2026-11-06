import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from history_of_x.core import key, save_json, read_json, public_text
from history_of_x.script import validate, CHAPTERS
from history_of_x.speech import caption_groups, align_written
from history_of_x.assets import allowed_license
from history_of_x.render import ass_time,srt_time,highlighted,shot_plan,write_ass,motion_filter
from history_of_x.gemini import Gemini,QuotaDeferred


def sample():
    return {'title':'Ethiopia','scenes':[{'scene_id':i+1,'chapter':c,'narration':'Ethiopia defended its independence.',
        'source_ids':['S1'],'visual_type':'map','subtitle_highlights':['Ethiopia'],'delivery':'normal'} for i,c in enumerate(CHAPTERS)]}

def test_script_order_and_citations():
    script=sample();assert validate(script,['S1'])==20
    script['scenes'][2]['chapter']='Roots'
    with pytest.raises(Exception,match='Five chapters'):validate(script,['S1'])
    script=sample();script['scenes'][0]['source_ids']=['invented']
    with pytest.raises(Exception,match='existing evidence'):validate(script,['S1'])

def test_banned_and_duplicate():
    script=sample();script['scenes'][0]['narration']='Let us delve into it.'
    with pytest.raises(Exception,match='banned'):validate(script,['S1'])
    script=sample();script['scenes'][1]['scene_id']=1
    with pytest.raises(Exception,match='unique'):validate(script,['S1'])

@pytest.mark.parametrize('value,expected',[('Public domain',True),('CC BY-SA 4.0',True),('CC0',True),('CC BY-NC 4.0',False),('CC BY-ND 3.0',False),('Copyrighted',False),('',False)])
def test_licenses(value,expected):assert allowed_license(value)==expected

def test_caption_groups_and_alignment():
    words=[{'word':w,'start':i*.4,'end':i*.4+.3} for i,w in enumerate('An army defended Ethiopia at Adwa.'.split())]
    groups=caption_groups(words)
    assert all(len(x['text'].split())<=3 for x in groups)
    aligned=align_written('An army defended Ethiopia at Adwa.',words)
    assert ' '.join(x['word'] for x in aligned)=='An army defended Ethiopia at Adwa.'
    assert not any(x['interpolated'] for x in aligned)

def test_alignment_preserves_misrecognized_names():
    words=[{'word':w,'start':i,'end':i+.8} for i,w in enumerate(['Menelik','defended','at','Add','wa'])]
    result=align_written('Menelik defended Ethiopia at Adwa.',words)
    assert result[2]['word']=='Ethiopia'
    assert all(a['end']<=b['start'] for a,b in zip(result,result[1:]))

def test_json_atomic_and_hash(tmp_path):
    p=tmp_path/'nested'/'state.json';save_json(p,{'a':1})
    assert read_json(p)=={'a':1}
    assert key({'a':1,'b':2})==key({'b':2,'a':1})
    assert not list(p.parent.glob('*.tmp'))

def test_caption_time_and_injection():
    assert ass_time(3661.23)=='1:01:01.23'
    assert srt_time(3661.234)=='01:01:01,234'
    assert '{' not in public_text('{\\move(0,0)}Ethiopia')
    assert r'\c&H75D8F2&' in highlighted('Ethiopia fought',['Ethiopia'])

def test_shots_bounded_and_motion():
    shots=shot_plan(24,[{'absolute_path':'photo.jpg'}],Path('map.jpg'),profile='cinematic')
    assert len(shots)==4 and sum(x['seconds'] for x in shots)==24
    assert len({x['motion'] for x in shots})==4
    assert 'zoompan' in motion_filter(180,1920,1080,30,0)

class FakeModels:
    def __init__(self):self.calls=0
    def generate_content(self,**kwargs):
        self.calls+=1
        return SimpleNamespace(text='{"ok":true}', candidates=[SimpleNamespace(finish_reason='STOP')],usage_metadata=None)

def test_pacing_cache_and_daily_budget(monkeypatch,tmp_path):
    monkeypatch.setenv('GEMINI_MODEL','gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_REQUEST_BUDGET','2')
    now=[1000.0];delays=[]
    def sleep(seconds):delays.append(seconds);now[0]+=seconds
    models=FakeModels();g=Gemini(tmp_path,client=SimpleNamespace(models=models),clock=lambda:now[0],sleeper=sleep)
    assert g.generate('A',{})=='{"ok":true}'
    assert g.generate('A',{})=='{"ok":true}'
    g.generate('B',{})
    assert models.calls==2 and delays==[65.0]
    with pytest.raises(QuotaDeferred):g.generate('C',{})

def test_unauthorized_model_rejected(monkeypatch,tmp_path):
    monkeypatch.setenv('GEMINI_MODEL','unverified-paid-model')
    with pytest.raises(Exception,match='free allowlist'):Gemini(tmp_path,client=SimpleNamespace())

def test_truncated_response_not_cached(monkeypatch,tmp_path):
    monkeypatch.setenv('GEMINI_MODEL','gemini-2.5-flash')
    models=SimpleNamespace(generate_content=lambda **kw:SimpleNamespace(text='{"partial":',candidates=[SimpleNamespace(finish_reason='MAX_TOKENS')]))
    g=Gemini(tmp_path,client=SimpleNamespace(models=models),clock=lambda:1000,sleeper=lambda _:None)
    with pytest.raises(Exception,match='truncated'):g.generate('A',{})
    assert len(list(tmp_path.glob('*.json')))==1

def test_shared_ledger_applies_to_separate_episode_directories(monkeypatch,tmp_path):
    monkeypatch.setenv('GEMINI_MODEL','gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_LEDGER_PATH',str(tmp_path/'shared'/'usage.json'))
    monkeypatch.setenv('GEMINI_REQUEST_BUDGET','1')
    client=SimpleNamespace(models=FakeModels())
    Gemini(tmp_path/'one',client=client,clock=lambda:1000,sleeper=lambda _:None).generate('one',{})
    other=Gemini(tmp_path/'two',client=client,clock=lambda:1000,sleeper=lambda _:None)
    with pytest.raises(QuotaDeferred):other.generate('two',{})

def test_portrait_layout_keeps_full_subject(tmp_path):
    from PIL import Image,ImageDraw
    from history_of_x.render import prepare_image
    source=tmp_path/'portrait.jpg';output=tmp_path/'prepared.jpg'
    im=Image.new('RGB',(600,1000),(220,220,220));d=ImageDraw.Draw(im)
    d.rectangle((100,100,500,900),fill=(200,20,20));im.save(source)
    prepare_image(source,output,960,540,'standard')
    with Image.open(output) as result:
        # A centered full portrait has pale margins at its top and bottom; a fill crop loses these.
        assert result.getpixel((result.width//2,round(result.height*.09)))[0]>100
        assert result.size==(1133,637)

def test_visible_credits_include_required_attribution():
    from history_of_x.credits import credit_lines
    a={'1':{'assets':[{'source_url':'https://commons.wikimedia.org/wiki/File:Example.jpg','title':'File:Example.jpg',
        'artist':'Example Creator','license':'CC BY 4.0','license_url':'https://creativecommons.org/licenses/by/4.0/'}]}}
    text=' '.join(credit_lines(a,['titan']))
    assert 'Example Creator' in text and 'Scott Buckley' in text
    assert 'creativecommons.org/licenses/by/4.0/' in text

def test_chapter_checkpoint_merge_and_missing_audio(tmp_path):
    from history_of_x.speech_merge import merge
    script=sample()
    for i in range(1,6):
        directory=tmp_path/f'chapter-{i}'
        directory.mkdir()
        (directory/'take.wav').write_bytes(b'test fixture')
        save_json(directory/'speech.json',{'voice':'warguy','scenes':[{'scene_id':i,'audio':'take.wav','verification':{'accepted':True}}]})
    merged=merge(script,'warguy',tmp_path)
    assert len(merged['scenes'])==5
    assert merged['scenes'][2]['audio']=='chapter-3/take.wav'
    (tmp_path/'chapter-3'/'take.wav').unlink()
    with pytest.raises(Exception,match='missing audio'):merge(script,'warguy',tmp_path)

def test_chapter_merge_rejects_voice_mismatch(tmp_path):
    from history_of_x.speech_merge import merge
    directory=tmp_path/'chapter-1';directory.mkdir()
    save_json(directory/'speech.json',{'voice':'kit-laser','scenes':[]})
    with pytest.raises(Exception,match='Narrator mismatch'):merge(sample(),'warguy',tmp_path)

def test_api_diagnostic_pacing_and_redaction(tmp_path):
    import importlib.util
    spec=importlib.util.spec_from_file_location('free_probes',Path(__file__).resolve().parents[1]/'scripts'/'check_free_models.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    class Failure(Exception):
        code=429
        message='quota exceeded sensitive-key'
    class Models:
        def __init__(self):self.calls=0
        def generate_content(self,**kwargs):
            self.calls+=1
            if self.calls==1:raise Failure()
            return SimpleNamespace(text='{"status":"ok"}',usage_metadata=None)
    sleeps=[]
    result=module.probe(SimpleNamespace(models=Models()),'sensitive-key',tmp_path/'check.json',sleeper=sleeps.append)
    assert sleeps==[65,65] and len(result)==3
    assert not result[0]['ok'] and result[1]['ok']
    assert 'sensitive-key' not in json.dumps(result)
