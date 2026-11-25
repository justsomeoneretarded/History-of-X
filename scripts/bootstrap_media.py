"""Verify media tools; install maintained Ubuntu packages on GitHub-hosted runners."""
from __future__ import annotations
import os,platform,shutil,subprocess

def usable():
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):return False
    result=subprocess.run(['ffmpeg','-hide_banner','-filters'],capture_output=True,text=True,timeout=20)
    return result.returncode==0 and ' ass ' in result.stdout and ' loudnorm ' in result.stdout

def main():
    if not usable():
        if platform.system()!='Linux' or os.getenv('GITHUB_ACTIONS')!='true':
            raise SystemExit('Install FFmpeg with libass, loudnorm and ffprobe for this platform.')
        print('Installing maintained Ubuntu media packages (FFmpeg, Cairo and fonts).',flush=True)
        common=['-o','Acquire::Retries=2','-o','Acquire::http::Timeout=30','-o','Acquire::https::Timeout=30']
        subprocess.run(['sudo','apt-get',*common,'update'],check=True,timeout=240)
        subprocess.run(['sudo','apt-get',*common,'install','-y','--no-install-recommends','ffmpeg','libcairo2','fonts-dejavu-core'],check=True,timeout=600)
    if not usable():raise SystemExit('FFmpeg is missing required subtitle/loudness filters.')
    print(subprocess.run(['ffmpeg','-version'],capture_output=True,text=True,check=True).stdout.splitlines()[0])

if __name__=='__main__':main()
