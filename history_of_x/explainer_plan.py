"""Evidence-constrained writing and Gemini direction of speech-timed visual beats."""
from __future__ import annotations
import math,re
from .core import PipelineError,key,read_json,save_json
from .script import CHAPTERS,BANNED,scene_schema,normalize_script,validate
from .vector_art import ICONS,PALETTE

DIRECTION='''Write an ORIGINAL animated historical explainer: brisk, conversational, witty and deadpan.
Humor comes from documented human decisions, bureaucracy, contradictions and overconfidence, never victims, famine or massacres.
No copied creator jokes, catchphrases, characters or songs. No fabricated quotations or made-up facts.
Explain political motives and consequences with nuance. Vary sentence lengths, use natural transitions through centuries.
No channel introductions, subscribe requests or stage directions in narration. No jargon unless explained.
Five ordered chapters: Hook, Roots, Catalyst, Turning Point, Aftermath. Start with a concrete surprising decision.
Each scene cites supplied source IDs, with dates matching those sources. State the historical endpoint explicitly.
Avoid these words/phrases: '''+', '.join(BANNED)

def write(api,title,brief,minutes,evidence,directory):
 from .script import generate_chapters
 identity=key('animated-script-v2-chapters',title,brief,minutes,evidence);output=directory/'script.json'
 if output.exists() and read_json(output).get('fingerprint')==identity:return read_json(output)
 class ChapterWriter:
  def generate(self,instruction,payload,max_output=6000,schema=None):
   # Small chapter grammars keep useful length constraints without a huge full-film grammar.
   style=DIRECTION.replace('Five ordered chapters: Hook, Roots, Catalyst, Turning Point, Aftermath. Start with a concrete surprising decision.', 'This is one chapter of a five-chapter film. Follow the specific chapter restriction below. The opening chapter starts with a concrete surprising decision.')
   return __import__('json').dumps(api.text(style+'\n'+instruction,payload,schema,max_output=max_output,preserve_bounds=True))
 result=generate_chapters(ChapterWriter(),title,brief,minutes,evidence,directory,identity)
 result['provenance']='Gemini chapter drafts and evidence-constrained chapter revisions for an original animated explainer'
 save_json(output,result);return result

def timing_beats(words,total,chapter):
 """Each visual is 3–6 seconds where chapter length permits; exact ASR-aligned words."""
 if total<=0:raise PipelineError('Nonpositive speech duration')
 count=max(1,round(total/4.5));span=total/count
 # Assign words by midpoint; no loss or duplication, even at a cut.
 beats=[]
 for i in range(count):
  start=i*span;end=(i+1)*span
  assigned=[w for w in words if start <= (w['start']+w['end'])/2 < end or (i==count-1 and (w['start']+w['end'])/2>=end)]
  beats.append({'beat_id':f'{chapter}-{i+1}','chapter':chapter,'start':start,'end':end,'text':' '.join(w['word'] for w in assigned)})
 return beats

def board_schema(ids):
 node={'type':'object','required':['icon','label','color'],'properties':{'icon':{'type':'string','enum':list(ICONS)},'label':{'type':'string','maxLength':20},'color':{'type':'string','enum':['coral','teal','gold','violet','blue','pink']}}}
 shot={'type':'object','required':['beat_id','headline','year_label','year','background','action','nodes','sting','music_mood','rationale'],'properties':{
  'beat_id':{'type':'string','enum':ids},'headline':{'type':'string','maxLength':35},'year_label':{'type':'string','maxLength':22},'year':{'type':'integer','minimum':-5000,'maximum':2030},
  'background':{'type':'string','enum':['cream','navy']},'action':{'type':'string','enum':['reveal','clash','exchange','rise','fracture','march','balance']},
  'nodes':{'type':'array','minItems':1,'maxItems':4,'items':node},'music_mood':{'type':'string','enum':['neutral','tense','somber','playful']},'sting':{'type':'boolean'},'rationale':{'type':'string'}}}
 return {'type':'object','required':['shots'],'properties':{'shots':{'type':'array','minItems':len(ids),'maxItems':len(ids),'items':shot}}}

def direct(api,script,speech,directory):
 allshots=[];position=0
 for i,(scene,spoken) in enumerate(zip(script['scenes'],speech['scenes'])):
  beats=timing_beats(spoken['words'],spoken['duration'],scene['scene_id'])
  ids=[b['beat_id'] for b in beats]
  # Generate an entire chapter batch, below, rather than a request for every shot.
  allshots.extend([{**b,'scene_id':scene['scene_id'],'narration_context':scene['narration'],'date_context':scene.get('date_label',''),'global_start':position+b['start'],'global_end':position+b['end']} for b in beats])
  position+=spoken['duration']
 result=[]
 for chapter in CHAPTERS:
  beats=[b for b in allshots if script['scenes'][b['scene_id']-1]['chapter']==chapter]
  ids=[b['beat_id'] for b in beats]
  identity=key('board-v2',beats);cache=directory/'boards'/(identity+'.json')
  if cache.exists():part=read_json(cache)
  else:
   prompt='''You are the motion director for an original, slick, colourful, flat animated history explainer.
Design EACH supplied beat around the actual words being spoken, considering surrounding narration. No generic scenery or repeated maps.
Use simple, instantly readable compositions: 1–4 illustrated objects/people, relationship, brief meaningful labels.
Show the historical subject: ruler for ruler, treaty for treaty, ship and coins for trade, competing documents for translation.
The headline should be 0–4 essential words. Node labels are optional, 0–2 words. NEVER put channel names, source/reference labels, technical notes, watermarks or decorative filler in visible text.
A running year display is required: year_label reflects the current narrated period, with c. for approximate dates and ranges when needed. year is an approximate numeric anchor for timeline ordering; never imply an invented exact date.
Differentiate adjoining compositions using node count, palette, layout and action. Set music_mood to fit the actual spoken passage: somber for suffering, tense for conflict, playful only for harmless irony. Keep primary actors recognizable by consistent role and label.
The palette and available icon vocabulary are in the schema. Do not ask for photographs. All symbols are original simplified illustrations, not literal historical portraits.
Stings must be rare (maximum one per chapter), at a genuine nontragic deadpan beat. Never use a sting for suffering or war deaths.
Return one shot per supplied beat_id, preserving order and all IDs. rationale explains relevance for internal QA ONLY.'''
   part=api.text(prompt,{'title':script['title'],'chapter':chapter,'beats':beats},board_schema(ids),max_output=18000)
   save_json(cache,part)
  shots=part.get('shots',[])
  if [s['beat_id'] for s in shots]!=ids:raise PipelineError('Storyboard omitted or reordered beats')
  stings=0
  for b,s in zip(beats,shots):
   if not 1<=len(s['nodes'])<=4:raise PipelineError('Storyboard needs 1–4 subjects per beat')
   if any(n['icon'] not in ICONS for n in s['nodes']):raise PipelineError('Unknown illustration')
   visible=' '.join([s['headline'],s['year_label'],*[n['label'] for n in s['nodes']]])
   if re.search(r'\b(history of x|source|reference|subscribe|chapter)\b',visible,re.I):raise PipelineError('Unnecessary on-screen chrome rejected')
   if s['sting']:stings+=1
   s['sting']=s['sting'] and stings<=1 and not re.search(r'\b(famine|massacre|killed|deaths|atrocit|terror|repression|starv)',b['narration_context'],re.I)
   result.append({**b,**s})
 save_json(directory/'storyboard.json',result);return result
