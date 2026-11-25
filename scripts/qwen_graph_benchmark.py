"""Real CPU-only Qwen direction benchmark; no API key and no production cache edits."""
from __future__ import annotations
import base64,json,os,subprocess,time
from pathlib import Path
import requests
from PIL import Image,ImageDraw
from history_of_x.core import ROOT,PipelineError,save_json
from history_of_x.rig_director import CONTRACT,schema,_program
from history_of_x.scene_film import render_scene
from history_of_x.cairo_scene import CairoCompositor

MODEL="qwen3:4b-instruct-2507-q4_K_M"
IMAGE="ollama/ollama:0.12.10"
NAME="history-qwen-benchmark"
URL="http://127.0.0.1:11434"
output=ROOT/"output/qwen-benchmark";output.mkdir(parents=True,exist_ok=True)
models=ROOT/"work/models/ollama";models.mkdir(parents=True,exist_ok=True)
deadline=time.monotonic()+1500
def command(args,seconds=600):
 result=subprocess.run(args,capture_output=True,text=True,timeout=min(seconds,max(1,deadline-time.monotonic())))
 if result.returncode:
  print("QWEN_SETUP_ERROR "+result.stderr[-3000:],flush=True)
  result.check_returncode()
 print("QWEN_SETUP "+str(args[:3])+" "+result.stdout.strip()[-300:],flush=True)
 return result
started=time.monotonic();launched=False;metrics=[]
try:
 command(["docker","pull",IMAGE])
 command(["docker","run","--detach","--rm","--name",NAME,
          "--publish","127.0.0.1:11434:11434",
          "--volume",str(models.resolve())+":/models",
          "--env","OLLAMA_MODELS=/models","--env","OLLAMA_HOST=0.0.0.0:11434",
          "--memory","8g","--cpus",str(min(4,os.cpu_count() or 2)),IMAGE])
 launched=True
 for _ in range(60):
  try:
   ready=requests.get(URL+"/api/version",timeout=2)
   if ready.ok:break
  except requests.RequestException:pass
  time.sleep(1)
 else:raise PipelineError("Local Ollama did not start")
 command(["docker","exec",NAME,"ollama","pull",MODEL])
 info=requests.post(URL+"/api/show",json={"model":MODEL},timeout=30)
 info.raise_for_status()
 save_json(output/"model-details.json",{"model":MODEL,"image":IMAGE,
  "details":info.json().get("details",{}),"model_info":info.json().get("model_info",{}),
  "runner_cpus":os.cpu_count(),"startup_seconds":time.monotonic()-started})
 narration="Menelik's wife, Empress Taytu, was no passive observer in these high-stakes politics. She helped organize resistance against encroaching colonial powers. Tensions peaked over the Treaty of Wuchale. Article seventeen was the trap. The Amharic text let Ethiopia choose diplomacy, while the Italian version made it mandatory, declaring a protectorate. Menelik spotted the deceit. He rejected their claim."
 context={"scene_id":"qwen-treaty-benchmark","narration":narration,"date":"1889",
  "duration":22.0,"reserved_archival_seconds":0,"approved_images":[],
  "timing":"0–6s Taytu's influence;6–10s treaty;10–17s optional versus compulsory;17–22s rejection."}
 programs=[];metrics=[];payload=context
 for attempt in range(2):
  begin=time.monotonic()
  response=requests.post(URL+"/api/chat",json={
   "model":MODEL,"stream":False,"format":schema(),
   "messages":[{"role":"system","content":CONTRACT},
               {"role":"user","content":json.dumps(payload,ensure_ascii=False)}],
   "options":{"num_ctx":8192,"num_predict":3500,
              "num_thread":min(4,os.cpu_count() or 2),"temperature":.35},
   "keep_alive":"30m"},timeout=(5,min(660,max(1,deadline-time.monotonic()))))
  response.raise_for_status();answer=response.json()
  metrics.append({"attempt":attempt+1,"seconds":time.monotonic()-begin,
   "model":answer.get("model"),"done_reason":answer.get("done_reason"),
   "prompt_tokens":answer.get("prompt_eval_count"),"output_tokens":answer.get("eval_count"),
   "decode_tokens_per_second":answer.get("eval_count",0)/max(1e-9,answer.get("eval_duration",0)/1e9)})
  raw=answer.get("message",{}).get("content","")
  (output/f"draft-{attempt}.txt").write_text(raw)
  try:
   if answer.get("done_reason")=="length":raise PipelineError("Local response exhausted its output token bound")
   spec=json.loads(raw);save_json(output/f"draft-{attempt}.json",spec)
   program=_program(spec,22.,[],"qwen-treaty-benchmark",0,[])
   program["generation_model"]=MODEL
   programs.append(program);break
  except (PipelineError,ValueError,KeyError,TypeError) as exc:
   save_json(output/f"draft-{attempt}-validation.json",{"error":str(exc)})
   if attempt:raise
   payload={**context,"previous_plan":raw,"validation_error":str(exc),
    "revision_request":"Return one complete corrected scene graph; keep all actions executable and reachable."}
 save_json(output/"metrics.json",{"model":MODEL,"image":IMAGE,"requests":metrics})
 print("QWEN_BENCHMARK "+json.dumps({"model":MODEL,"requests":metrics}),flush=True)
 program=programs[0];save_json(output/"scene-program.json",program)
 compositor=CairoCompositor(program,(640,360),recording=True)
 sheet=Image.new("RGB",(1920,780),"#173B38")
 for index,at in enumerate((.5,4,8,12,16,21)):
  frame=compositor.frame(at);x=(index%3)*640;y=(index//3)*390
  sheet.paste(frame,(x,y));ImageDraw.Draw(sheet).text((x+12,y+365),str(at)+"s",fill="white")
 sheet.save(output/"temporal.jpg",quality=90)
 encoded=base64.b64encode((output/"temporal.jpg").read_bytes()).decode()
 print("DIRECTOR_IMAGE_START",flush=True)
 for i in range(0,len(encoded),8000):print("DIRECTOR_IMAGE_CHUNK "+encoded[i:i+8000],flush=True)
 print("DIRECTOR_IMAGE_END",flush=True)
 before=time.monotonic();movie=render_scene(program,output,"cinematic")
 save_json(output/"render-metrics.json",{"movie":str(movie),"seconds":time.monotonic()-before,
  "duration_seconds":22.,"width":1920,"height":1080,"fps":30,"creative_review":"not performed"})
 print("QWEN_RENDER "+str(movie),flush=True)
except BaseException as exc:
 save_json(output/"failure.json",{"error":str(exc),"requests":metrics,
           "elapsed_seconds":time.monotonic()-started})
 raise
finally:
 if launched:
  # Keep only public model files in the mounted cache, owned by the runner.
  subprocess.run(["docker","exec",NAME,"chown","-R",str(os.getuid())+":"+str(os.getgid()),"/models"],timeout=45)
  subprocess.run(["docker","stop",NAME],timeout=45)
