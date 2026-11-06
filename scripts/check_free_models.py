"""Small, bounded real API probes; logs status/usage, never credentials."""
import json
import os
import time
from pathlib import Path
from google import genai,types
from history_of_x.core import save_json
secret=os.getenv('GEMINI_API')
if not secret:raise SystemExit('GEMINI_API is missing')
client=genai.Client(api_key=secret,http_options={'timeout':45000,'retry_options':{'attempts':1}})
rows=[]
for i,name in enumerate(['gemini-3.8-flash','gemini-3.5-flash-lite','gemini-3.1-flash-lite']):
    if i:time.sleep(65)
    started=time.monotonic()
    try:
        response=client.models.generate_content(model=name,contents='Return only the JSON object {"status":"ok"}.',
            config=types.GenerateContentConfig(max_output_tokens=128,response_mime_type='application/json',thinking_config=types.ThinkingConfig(thinking_level='low')))
        row={'model':name,'ok':bool(response.text),'seconds':round(time.monotonic()-started,2),
             'usage':response.usage_metadata.model_dump(mode='json') if response.usage_metadata else {}}
    except Exception as exc:
        message=str(getattr(exc,'message','')).replace(secret,'[REDACTED]')
        row={'model':name,'ok':False,'seconds':round(time.monotonic()-started,2),'code':getattr(exc,'code',None),'message':message[:1800]}
    rows.append(row);print(json.dumps(row),flush=True)
    save_json(Path('output/free-model-check.json'),rows)
if not any(x['ok'] for x in rows):raise SystemExit('No model probe succeeded; inspect the saved status and quota messages.')
