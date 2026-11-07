"""Real free-tier TTS capability check. Never logs credentials or audio base64."""
import os,time,base64,wave,io
from pathlib import Path
import requests
from history_of_x.core import save_json
root=Path('output/media-check');root.mkdir(parents=True,exist_ok=True)
secret=os.environ['GEMINI_API'];headers={'x-goog-api-key':secret}
models=requests.get('https://generativelanguage.googleapis.com/v1beta/models',headers=headers,timeout=45)
if models.ok:
 save_json(root/'models.json',[{k:v for k,v in m.items() if k in ('name','supportedGenerationMethods','inputTokenLimit','outputTokenLimit')} for m in models.json().get('models',[])])
body={'model':'gemini-3.8-flash-tts','input':[{'type':'user_input','content':[{'type':'text','text':'In eighteen ninety-six, Italy expected an easy victory. Ethiopia had other plans. The paperwork was about to become a battlefield.','annotations':[{'type':'speech_metadata','style':'An engaging history explainer. Dry, understated wit, conversational, clear and brisk. Never announcer-like.'}]}]}],'response_format':{'type':'audio'},'generation_config':{'speech_config':[{'voice':'Puck'}]},'store':False}
start=time.monotonic();r=requests.post('https://generativelanguage.googleapis.com/v1beta/interactions',headers={**headers,'Content-Type':'application/json'},json=body,timeout=150)
report={'model':body['model'],'status':r.status_code,'seconds':round(time.monotonic()-start,2)}
if r.ok:
 data=r.json();save_json(root/'response-structure.json',{k:v for k,v in data.items() if k not in ('steps','output_audio')})
 blocks=[c for s in data.get('steps',[]) if s.get('type')=='model_output' for c in s.get('content',[]) if c.get('type')=='audio']
 if blocks:
  b=blocks[-1];raw=base64.b64decode(b['data']);(root/'gemini-puck.wav').write_bytes(raw)
  report.update(bytes=len(raw),mime_type=b.get('mime_type'),audio_fields=[k for k in b if k!='data'])
 else: report['error']='No audio block';report['keys']=list(data)
else:report['error']=r.text.replace(secret,'[REDACTED]')[:1600]
save_json(root/'check.json',report);print(report)
if not r.ok or not report.get('bytes'):raise SystemExit(1)
