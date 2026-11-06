from pathlib import Path
import shutil
import subprocess
import pytest
from PIL import Image
from history_of_x.core import duration, ffmpeg, probe
from history_of_x.render import render_scene

@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='ffmpeg required')
def test_real_motion_render_and_resume(tmp_path):
    source=tmp_path/'test.jpg'
    image=Image.new('RGB',(1200,800),(60,110,150))
    from PIL import ImageDraw
    draw=ImageDraw.Draw(image);draw.rectangle((200,200,800,600),fill=(180,130,40));image.save(source)
    scene={'scene_id':1,'visual_type':'photograph'}
    spoken={'duration':1.25}
    records=[{'absolute_path':str(source),'source_url':'https://example.org/art'}]
    output=render_scene(scene,spoken,records,source,tmp_path,'draft')
    assert abs(duration(output)-1.25)<.1
    assert probe(output)['streams'][0]['width']==960
    modified=output.stat().st_mtime_ns
    assert render_scene(scene,spoken,records,source,tmp_path,'draft')==output
    assert output.stat().st_mtime_ns==modified
