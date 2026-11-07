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
 """One Gemini choreography call per chapter; no redundant icon-card planning."""
 from .motion_director import direct as choreograph
 shots=[];position=0
 for scene,spoken in zip(script['scenes'],speech['scenes']):
  for b in timing_beats(spoken['words'],spoken['duration'],scene['scene_id']):
   shots.append({**b,'scene_id':scene['scene_id'],'narration_context':scene['narration'],'date_context':scene.get('date_label',''),'year_label':scene.get('date_label',''),'global_start':position+b['start'],'global_end':position+b['end'],'headline':'','nodes':[],'sting':False,'music_mood':'neutral','rationale':'Physical action matched to narration'})
  position+=spoken['duration']
 result=choreograph(api,script,shots,directory);save_json(directory/'storyboard.json',result);return result
