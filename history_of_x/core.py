from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
class PipelineError(RuntimeError):
    pass

def key(*values):
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]

def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(handle, 'w') as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False, default=lambda x: x.item())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)

def read_json(path):
    return json.loads(Path(path).read_text())

def run(args, timeout=900, **kwargs):
    try:
        result = subprocess.run([str(x) for x in args], capture_output=True, text=True, timeout=timeout, **kwargs)
    except subprocess.TimeoutExpired as e:
        raise PipelineError(f'{args[0]} exceeded {timeout}s deadline') from e
    if result.returncode:
        raise PipelineError(f'{args[0]} failed: {result.stderr[-2500:]}')
    return result.stdout

def ffmpeg(*args, timeout=900):
    return run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y', *args], timeout=timeout)

def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', path]))

def duration(path):
    return float(probe(path)['format']['duration'])

def normalized(text):
    return ' '.join(re.findall(r'\w+', text.casefold()))

def slug(text):
    return re.sub('[^a-z0-9]+', '-', text.lower()).strip('-')[:70] or 'episode'

def public_text(value):
    # Plain text safe for subtitle and annotation formats; never treated as a shell command.
    return re.sub(r'[{}\\\x00-\x08\x0b-\x1f]', '', str(value)).strip()
