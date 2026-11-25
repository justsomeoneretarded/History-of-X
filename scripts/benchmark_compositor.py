"""Measure the actual alternative compositor and render a visual comparison."""
import base64,json,os
from time import perf_counter
import numpy as np
from PIL import Image,ImageDraw
from history_of_x.core import ROOT
from history_of_x.rig_scene import compile_scene
from history_of_x.scene_film import scene_frame,_raster_layers,render_scene
from history_of_x.cairo_scene import CairoCompositor

spec=json.loads((ROOT/"assets/style/rig-demo.json").read_text())
program=compile_scene(spec,15,scene_id="original-rig-demo")
backend=os.getenv("BENCHMARK_COMPOSITOR","cairo");recording=backend=="vector"
raster=None if recording else _raster_layers(program,1.5)
compositor=CairoCompositor(program,(1920,1080),raster,1.5,recording=recording)
for label,times in (("held",[3+i/30 for i in range(40)]),
                    ("camera-and-acting",[6+i/30 for i in range(40)])):
 start=perf_counter()
 for at in times:compositor.frame(at)
 elapsed=perf_counter()-start
 print("COMPOSITOR_PROFILE",backend,label,round(elapsed,3),"seconds",round(len(times)/elapsed,2),"fps",flush=True)
output=ROOT/"output/rig-demo";output.mkdir(parents=True,exist_ok=True)
small_raster=_raster_layers(program,1.5)
small=CairoCompositor(program,(640,360),None if recording else small_raster,1.5,recording=recording)
sheet=Image.new("RGB",(1920,780),"#173B38")
for index,at in enumerate([0,2.2,5.2,7,11.2,13.2]):
 actual=small.frame(at);reference=scene_frame(program,at,(640,360),small_raster,1.5)
 error=np.abs(np.asarray(actual,dtype=float)-np.asarray(reference,dtype=float))
 print("COMPOSITOR_COMPARE",at,"mean_error",round(float(error.mean()),4),
       "pixels_over_30",round(float((error.max(axis=2)>30).mean()),5),flush=True)
 x=(index%3)*640;y=(index//3)*390;sheet.paste(actual,(x,y))
 ImageDraw.Draw(sheet).text((x+12,y+365),str(at)+"s",fill="white")
sheet.save(output/"contact-and-reaction.jpg",quality=90)
encoded=base64.b64encode((output/"contact-and-reaction.jpg").read_bytes()).decode()
print("DIRECTOR_IMAGE_START",flush=True)
for i in range(0,len(encoded),8000):print("DIRECTOR_IMAGE_CHUNK "+encoded[i:i+8000],flush=True)
print("DIRECTOR_IMAGE_END",flush=True)
start=perf_counter();movie=render_scene(program,output,"cinematic",backend=backend)
print("COMPOSITOR_MOVIE",backend,str(movie),"elapsed_seconds",round(perf_counter()-start,3),flush=True)
