"""Render a provider-free original acting sample for direct temporal inspection."""
import base64
import json
from pathlib import Path
from PIL import Image,ImageDraw
from history_of_x.core import ROOT,save_json
from history_of_x.rig_scene import compile_scene
from history_of_x.scene_film import scene_frame,render_scene

output=ROOT/"output"/"rig-demo";output.mkdir(parents=True,exist_ok=True)
spec=json.loads((ROOT/"assets/style/rig-demo.json").read_text())
program=compile_scene(spec,15,scene_id="original-rig-demo")
save_json(output/"scene-program.json",program)
# Show contact, ownership transfer, discovery, placing and refusal.
times=[0,2.2,5.2,7,11.2,13.2]
sheet=Image.new("RGB",(1920,780),"#173B38")
for index,at in enumerate(times):
 frame=scene_frame(program,at,(640,360))
 x=(index%3)*640;y=(index//3)*390
 sheet.paste(frame,(x,y))
 ImageDraw.Draw(sheet).text((x+12,y+365),str(at)+"s",fill="white")
sheet.save(output/"contact-and-reaction.jpg",quality=90)
encoded=base64.b64encode((output/"contact-and-reaction.jpg").read_bytes()).decode()
print("DIRECTOR_IMAGE_START",flush=True)
for i in range(0,len(encoded),8000):print("DIRECTOR_IMAGE_CHUNK "+encoded[i:i+8000],flush=True)
print("DIRECTOR_IMAGE_END",flush=True)
movie=render_scene(program,output,"cinematic")
print("ORIGINAL_RIG_DEMO "+str(movie),flush=True)
