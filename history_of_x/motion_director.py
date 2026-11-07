"""Gemini action choreography; existing narration is immutable."""
from pathlib import Path
from .core import ROOT,PipelineError,key,read_json,save_json
from .script import CHAPTERS
ENVIRONMENTS=['harbor','palace','council','treaty','workshop','city','church','assembly','rebuild','highlands','camp']
ACTIVITIES=['trade','walk','build','negotiate','debate','write','treaty','march','battle','retreat','fire','rally','talk']
CAMERAS=['wide','medium','close','tracking']

def schema(ids):
 props={'beat_id':{'type':'string','enum':ids},'year_label':{'type':'string'},'sting':{'type':'boolean'},'music_mood':{'type':'string','enum':['neutral','tense','somber','playful']},'environment':{'type':'string','enum':ENVIRONMENTS},'activity':{'type':'string','enum':ACTIVITIES},'camera':{'type':'string','enum':CAMERAS},'lead_role':{'type':'string','enum':['ruler','queen','official','worker','soldier','italian']},'opponent_role':{'type':'string','enum':['ruler','queen','official','worker','soldier','italian']},'photo_id':{'type':'string'},'direction':{'type':'string'}}
 return {'type':'object','required':['shots'],'properties':{'shots':{'type':'array','items':{'type':'object','required':list(props),'properties':props}}}}

def photos():
 manifest=read_json(ROOT/'assets'/'presets'/'ethiopia'/'manifest.json');result={}
 for item in manifest:
  if 'public domain' in item.get('license','').lower() and any(x in item['title'].lower() for x in ['menelik','taytu','baratieri','mengistu','haile selassie']):
   result[Path(item['bundled_path']).stem]=item
 result.update(read_json(ROOT/'assets'/'footage'/'photographs.json'))
 return result

def direct(api,script,shots,directory):
 output=directory/'motion-storyboard.json';catalog=photos() if 'ethiop' in script['title'].lower() else {}
 results=[];starts={};activity_starts={}
 for shot in shots:starts.setdefault(shot['scene_id'],shot['global_start'])
 for chapter in CHAPTERS:
  beats=[s for s in shots if script['scenes'][s['scene_id']-1]['chapter']==chapter];ids=[s['beat_id'] for s in beats]
  if not beats:continue
  fingerprint=key('motion-direction-v1',beats,catalog);cache=directory/'motion-plans'/(fingerprint+'.json')
  if cache.exists():plan=read_json(cache)
  else:
   prompt='''Direct a MOVING animated historical film, never a slideshow or an animated PowerPoint.
Narration is already recorded: do not rewrite it. Each beat belongs to a continuous story scene.
Choose a physical environment and sustained character ACTION for every beat. Scenes have articulated stick figures with jointed arms and legs, moving ships, waves, clouds, crowds, props and smoke. People must do things: carry goods, negotiate, write, dispute a treaty, march through terrain, build, rally or retreat. Avoid static poses and bouncing icons.
Choose lead_role and opponent_role to fit the people described; use official or soldier for commanders, not a crown on every leader.
Keep neighboring beats in a compatible environment for continuity; change camera between wide/medium/close/tracking every few beats. Differentiate action with the spoken phrase, not arbitrary transitions.
Use harbor/trade for commerce; palace/council for government; treaty with negotiate/write/debate for diplomacy; church/city/build for development; highlands or camp with march/battle/retreat for campaigns; assembly for political speech; rebuild for aftermath.
Do not make all environments highlands. Never show a battle for ordinary political disagreement or a comedic action for suffering.
Historical photo IDs are optional. Include a relevant actual portrait when its person is the spoken subject. The Cleveland gospel leaf is a real medieval Ethiopian manuscript: use it for church/religious legitimacy passages, not as a portrait. Include relevant genuine imagery, but do not force unrelated photos. Empty photo_id means no photograph. Do not invent IDs.
Keep year_label aligned with the spoken era. Choose an appropriate music_mood, with a rare sting only for harmless irony (never for suffering). Return every supplied beat_id exactly once in order. direction is internal choreography commentary, never an on-screen heading. No channel/source/reference words in the picture.'''
   plan=api.text(prompt,{'title':script['title'],'chapter':chapter,'beats':[{'beat_id':s['beat_id'],'words':s['text'],'context':s['narration_context'],'year':s['year_label']} for s in beats], 'photographs':[{'id':k,'subject':v['title']} for k,v in catalog.items()]},schema(ids),max_output=10000)
   save_json(cache,plan)
  if [s['beat_id'] for s in plan['shots']]!=ids:raise PipelineError('Motion director omitted/reordered beats')
  for old,new in zip(beats,plan['shots']):
   photo=catalog.get(new['photo_id']);motion={**new,'year_label':new.get('year_label',old['year_label']),'scene_time':old['global_start']-starts[old['scene_id']]}
   previous=activity_starts.get(old['scene_id'])
   if not previous or previous[0]!=new['activity']:activity_starts[old['scene_id']]=(new['activity'],motion['scene_time'])
   motion['action_start_time']=activity_starts[old['scene_id']][1]
   if photo:motion['photo_path']=photo['bundled_path'];motion['photo_credit']=photo
   results.append({**old,'year_label':motion['year_label'],'music_mood':new.get('music_mood',old.get('music_mood','neutral')),'sting':new.get('sting',False),'motion':motion})
 save_json(output,results);return results
