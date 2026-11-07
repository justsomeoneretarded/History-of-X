"""Measure sustained subject-region changes, not subtitle animation or entrance effects."""
import subprocess
import numpy as np
from .core import PipelineError

def measure(video,start=1.2,end=None):
 args=['ffmpeg','-v','error','-ss',str(start),'-i',str(video)]
 if end is not None:args+=['-t',str(max(.25,end-start))]
 args+=['-vf','crop=iw:ih*0.70:0:ih*0.15,scale=160:90,fps=4','-an','-pix_fmt','rgb24','-f','rawvideo','-']
 r=subprocess.run(args,capture_output=True,timeout=120)
 if r.returncode:raise PipelineError('Cannot decode motion sample')
 count=len(r.stdout)//(160*90*3)
 if count<3:raise PipelineError('Motion sample is too short')
 frames=np.frombuffer(r.stdout,np.uint8).reshape(count,90,160,3).astype(np.int16)
 diff=np.abs(np.diff(frames,axis=0)).max(axis=3)
 ratios=(diff>12).mean(axis=(1,2))
 return {'median_changed_fraction':float(np.median(ratios)),'minimum_changed_fraction':float(np.min(ratios)),'active_window_fraction':float((ratios>.003).mean()),'sample_frames':count,'passed':bool(np.median(ratios)>.005 and (ratios>.003).mean()>.8)}
