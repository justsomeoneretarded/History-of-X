"""Diagnose model transport and schema separately, preserving safe reports."""
from pathlib import Path
from history_of_x.media_api import MediaAPI
from history_of_x.core import save_json
from history_of_x.script import scene_schema
api=MediaAPI(Path('work/text-adapter'))
rows=[]
for label,schema,prompt in [('tiny',{'type':'object','required':['status'],'properties':{'status':{'type':'string'}}},'Return status ok.'),('script-schema',scene_schema(['S1'],1200,18),'Write a miniature history explainer in exactly five scenes and five chapters Hook Roots Catalyst Turning Point Aftermath. Use source S1 for every scene. Source S1: Ethiopia defeated Italy at Adwa in 1896. Menelik II led Ethiopia. Explain only these facts; do not invent other facts. 100 spoken words total.')]:
 try:
  result=api.text(prompt,{},schema,max_output=4000);rows.append({'label':label,'ok':True,'keys':list(result)})
 except Exception as e:rows.append({'label':label,'ok':False,'error':str(e)})
 save_json(Path('output/text-adapter.json'),rows);print(rows[-1],flush=True)
