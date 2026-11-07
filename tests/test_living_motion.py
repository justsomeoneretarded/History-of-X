from pathlib import Path
import numpy as np
import pytest
from PIL import Image
from history_of_x.motion_canvas import Draw,actor,joint,render_shot
from history_of_x.motion_quality import measure
from history_of_x.core import PipelineError,duration

def test_jointed_character_changes_limbs_without_translating_its_root():
 images=[]
 for t in (2,2.3):
  im=Image.new('RGB',(1280,720),'white');actor(Draw(im,1),640,620,t,action='walk');images.append(np.asarray(im).astype(int))
 leg_change=(np.abs(images[0][490:635,560:725]-images[1][490:635,560:725]).max(axis=2)>12).mean()
 assert leg_change>.025

def test_two_link_joint_reaches_hand():
 import math
 a=(0,0);b=(60,40);k=joint(a,b,45,45)
 assert abs(math.dist(a,k)-45)<.001 and abs(math.dist(k,b)-45)<.001

def test_real_motion_persists_after_first_second(tmp_path):
 shot={'global_start':0,'global_end':3,'motion':{'environment':'harbor','activity':'trade','camera':'wide','year_label':'100 CE','scene_time':0}}
 v=render_shot(shot,tmp_path,'draft',0,3);q=measure(v,1.1,2.9)
 assert abs(duration(v)-3)<.1 and q['passed'] and q['active_window_fraction']>.8

def test_static_card_fails_motion_check(tmp_path):
 from history_of_x.core import ffmpeg
 im=Image.new('RGB',(960,540),'beige');im.save(tmp_path/'still.png')
 ffmpeg('-loop','1','-i',tmp_path/'still.png','-t','3','-c:v','libx264','-pix_fmt','yuv420p',tmp_path/'still.mp4')
 assert not measure(tmp_path/'still.mp4',1,2.8)['passed']

def test_new_renderer_does_not_fall_back_to_a_slideshow(tmp_path):
 with pytest.raises(PipelineError,match='motion'):
  render_shot({'global_start':0,'global_end':3},tmp_path,'draft',0,3)

def test_archive_bridge_preserves_voice_scene_and_dates():
 from history_of_x.archival_motion import bridge
 script={'title':'Ethiopia','scenes':[{'chapter':'Turning Point'},{'chapter':'Aftermath'}]}
 shots=[{'scene_id':1,'global_start':0,'global_end':4.5},{'scene_id':2,'global_start':4.5,'global_end':9}]
 result,gaps=bridge(script,shots)
 assert len(result)==4 and result[1]['year_label']=='1935'
 assert result[-1]['global_start']==13.5 and shots[-1]['global_start']==4.5
 assert gaps[0]['before_scene_id']==2 and gaps[0]['seconds']==9

def test_archival_gap_does_not_double_or_delay_later_speech(tmp_path):
 import soundfile as sf
 from history_of_x.audio_edit import assemble
 source=tmp_path/'speech';source.mkdir()
 for name,hz in [('first',440),('last',880)]:
  t=np.arange(48000)/24000;sf.write(source/(name+'.wav'),.1*np.sin(2*np.pi*hz*t),24000)
 speech={'scenes':[{'scene_id':1,'audio':'first.wav','duration':2},{'scene_id':2,'audio':'last.wav','duration':2}]}
 audio,timing=assemble(speech,source,tmp_path/'mix',[{'before_scene_id':2,'seconds':1}]);data,sr=sf.read(audio)
 assert timing['passed'] and abs(len(data)/sr-5)<.01
 assert np.max(np.abs(data[2*sr:3*sr]))<.001
 assert np.sqrt(np.mean(data[int(3.2*sr):int(4.8*sr)]**2))>.05
