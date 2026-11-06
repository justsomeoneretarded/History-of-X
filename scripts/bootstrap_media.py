"""Use installed media tools or a verified portable build; never wait on apt mirrors."""
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import urllib.request

URL='https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-11-06-12-50/ffmpeg-n8.1.3-34-ga35157abb9-linux64-gpl-8.1.tar.xz'
SHA256='2d17c1f53aa6e15882ff76d2a0089d63c3553a401bf2bdc723d798beb5eb4f1b'
root=Path('work/tools').resolve()
root.mkdir(parents=True,exist_ok=True)

def usable():
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):return False
    result=subprocess.run(['ffmpeg','-hide_banner','-filters'],capture_output=True,text=True,timeout=20)
    return result.returncode==0 and ' ass ' in result.stdout

if not usable() or os.getenv('FORCE_PORTABLE_FFMPEG')=='1':
    if platform.system()!='Linux' or platform.machine() not in ('x86_64','AMD64'):
        raise SystemExit('Install FFmpeg with libass and ffprobe for this platform.')
    archive=root/'ffmpeg-8.1.3.tar.xz'
    if not archive.exists():
        print('Downloading verified portable FFmpeg 8.1.3 (approximately 145 MB).',flush=True)
        with urllib.request.urlopen(URL,timeout=60) as response,archive.open('wb') as output:
            shutil.copyfileobj(response,output)
    observed=hashlib.sha256(archive.read_bytes()).hexdigest()
    print(f'Portable archive: {archive.stat().st_size} bytes, sha256={observed}',flush=True)
    if observed!=SHA256:
        archive.unlink(missing_ok=True)
        raise SystemExit('FFmpeg download checksum mismatch. No unverified executable was run.')
    with tarfile.open(archive) as source:
        for name in ['ffmpeg','ffprobe']:
            member=next(x for x in source.getmembers() if x.name.endswith('/'+name) and x.isfile())
            with source.extractfile(member) as data,(root/name).open('wb') as output:
                shutil.copyfileobj(data,output)
            (root/name).chmod(0o755)
    archive.unlink()
    os.environ['PATH']=str(root)+os.pathsep+os.environ['PATH']
    if not usable():raise SystemExit('Portable FFmpeg lacks required subtitle support.')
    if os.getenv('GITHUB_PATH'):
        with open(os.environ['GITHUB_PATH'],'a') as stream:stream.write(str(root)+'\n')
print(subprocess.run(['ffmpeg','-version'],capture_output=True,text=True,check=True).stdout.splitlines()[0])
