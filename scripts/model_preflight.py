"""Log only non-secret model metadata. Never log the key or a request URL containing it."""
import os
from pathlib import Path
from google import genai
from history_of_x.core import save_json
secret=os.getenv('GEMINI_API') or os.getenv('GEMINI_API_KEY')
if not secret:raise SystemExit('GEMINI_API is missing')
client=genai.Client(api_key=secret,http_options={'timeout':60000})
models=[]
for model in client.models.list():
    name=model.name or ''
    if any(x in name for x in ('flash','pro')):
        row={'name':name,'input_token_limit':model.input_token_limit,'output_token_limit':model.output_token_limit,
             'supported_actions':model.supported_actions}
        models.append(row)
        print(row)
Path('output').mkdir(exist_ok=True)
save_json(Path('output/models.json'),models)
