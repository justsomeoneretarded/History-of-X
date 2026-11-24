"""Bound inline video requests and use private Gemini Files transport for longer films."""
from __future__ import annotations
import base64,time
from contextlib import contextmanager
from pathlib import Path
from .core import PipelineError

@contextmanager
def video_part(api,path,inline_limit=12_000_000,client_factory=None,sleeper=time.sleep,clock=time.monotonic,processing_timeout=240):
    path=Path(path)
    if path.stat().st_size<=inline_limit:
        yield {'inlineData':{'mimeType':'video/mp4','data':base64.b64encode(path.read_bytes()).decode()}}
        return
    if client_factory is None:
        from google import genai
        client_factory=lambda:genai.Client(api_key=api.secret,http_options={'timeout':180000})
    client=client_factory();record=None
    try:
        record=client.files.upload(file=str(path),config={'mime_type':'video/mp4'})
        deadline=clock()+processing_timeout
        state=lambda item:str(getattr(getattr(item,'state',None),'name',getattr(item,'state',None))).split('.')[-1].upper()
        while state(record)=='PROCESSING':
            remaining=deadline-clock()
            if remaining<=0:raise PipelineError('Gemini review video exceeded its processing deadline')
            sleeper(min(10,remaining));record=client.files.get(name=record.name)
        if state(record)!='ACTIVE' or not getattr(record,'uri',None):
            raise PipelineError('Gemini did not make the review video available')
        yield {'fileData':{'mimeType':'video/mp4','fileUri':record.uri}}
    finally:
        if record is not None and getattr(record,'name',None):
            try:client.files.delete(name=record.name)
            except Exception:print('Gemini temporary review file cleanup was unavailable; provider expiry still applies.',flush=True)
        client.close()
