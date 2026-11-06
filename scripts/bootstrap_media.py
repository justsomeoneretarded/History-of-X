"""Use installed media tools or a verified portable build; never wait on apt mirrors."""
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import urllib.request

URL='https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz'
SHA256='abda8d77ce8309141f83ab8edf0596834087c52467f6badf376a6a2a4c87cf67'
root=Path('work/tools').resolve()
root.mkdir(parents=True,exist_ok=True)

def usable():
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):return False
    result=subprocess.run(['ffmpeg','-hide_banner','-filters'],capture_output=True,text=True,timeout=20)
    return result.returncode==0 and ' ass ' in result.stdout

if not usable() or os.getenv('FORCE_PORTABLE_FFMPEG')=='1':
    if platform.system()!='Linux' or platform.machine() not in ('x86_64','AMD64'):
        raise SystemExit('Install FFmpeg with libass and ffprobe for this platform.')
    archive=root/'ffmpeg-7.0.2.tar.xz'
    if not archive.exists():
        print('Downloading verified portable FFmpeg 7.0.2 (approximately 40 MB).',flush=True)
        with urllib.request.urlopen(URL,timeout=60) as response,archive.open('wb') as output:
            shutil.copyfileobj(response,output)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256:
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
