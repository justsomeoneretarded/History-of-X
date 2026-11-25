"""Bounded CPU profiling of real illustrated frames, without provider calls."""
import cProfile
import io
import json
import pstats
from time import perf_counter
from history_of_x.core import ROOT
from history_of_x.rig_scene import compile_scene
from history_of_x.scene_film import scene_frame,_raster_layers,_PatchCache

spec=json.loads((ROOT/"assets/style/rig-demo.json").read_text())
program=compile_scene(spec,15,scene_id="profile")
raster=_raster_layers(program,1.5)
for label,times in (("held",[3+i/30 for i in range(40)]),
                    ("camera-and-acting",[6+i/30 for i in range(40)])):
 cache=_PatchCache();profile=cProfile.Profile();start=perf_counter()
 profile.enable()
 for at in times:scene_frame(program,at,(1920,1080),raster,1.5,cache)
 profile.disable();elapsed=perf_counter()-start
 stream=io.StringIO();pstats.Stats(profile,stream=stream).sort_stats("cumtime").print_stats(18)
 print("RIG_PROFILE",label,round(elapsed,3),"seconds",round(len(times)/elapsed,2),"fps",flush=True)
 print(stream.getvalue(),flush=True)
