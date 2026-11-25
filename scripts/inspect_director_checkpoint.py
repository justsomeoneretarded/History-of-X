"""Inspect existing director programs without any provider call or credentials."""
import base64, copy, io, json, os, re
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw
from history_of_x.scene_film import scene_frame, validate_scene
from history_of_x.core import save_json

def preview_structure(program):
    """Preserve root paint order while making ungrouped static artwork inspectable."""
    program=copy.deepcopy(program)
    root=ET.fromstring(program['svg'])
    layers={item['id']:item for item in program['layers']}
    ids={item.get('id') for item in root.iter() if item.get('id')}
    order=[]
    for index,child in enumerate(list(root)):
        tag=child.tag.rsplit('}',1)[-1]
        if tag in {'defs','title','desc'}: continue
        identifier=child.get('id')
        if tag!='g':
            if not identifier:
                identifier='inspection_static_'+str(index)
                while identifier in ids: identifier+='x'
                ids.add(identifier)
            group=ET.Element('{http://www.w3.org/2000/svg}g',{'id':identifier})
            child.attrib.pop('id',None)
            root.remove(child)
            root.insert(index,group)
            group.append(child)
        elif not identifier:
            identifier='inspection_group_'+str(index)
            child.set('id',identifier)
        if identifier not in layers:
            layers[identifier]={'id':identifier,'pivot':[960,540],'start':0,
                'end':program['duration'],'keyframes':[{'time':0}]}
        order.append(identifier)
    program['svg']=ET.tostring(root,encoding='unicode')
    program['layers']=[layers[identifier] for identifier in order]
    return program

directory=Path('work/director/scene-programs')
out=Path('output/inspection')
out.mkdir(parents=True,exist_ok=True)
paths=sorted(directory.rglob('*-draft-*.json'))
if not paths: paths=sorted(directory.rglob('*.json'))
from history_of_x.scene_film import acted_treaty_proof
capability=out/'original-acting-capability.json'
save_json(capability,acted_treaty_proof())
paths.append(capability)
from history_of_x.director_script import chapter_story_issues, chapter_style_issues
from history_of_x.script import CHAPTERS
outline_path=Path('work/director/outline.json')
if outline_path.exists():
    outline=json.loads(outline_path.read_text())
    fingerprint=outline.get('fingerprint','')
    if fingerprint:
        for path in sorted(Path('work/director/director-chapters').glob('*-'+fingerprint+'.json')):
            chapter=CHAPTERS[int(path.name.split('-',1)[0])-1]
            saved=json.loads(path.read_text())
            try:
                issues=chapter_story_issues(saved,chapter)+chapter_style_issues(saved)
            except Exception as exc:
                issues=[str(exc)]
            print('SAVED_CHAPTER '+json.dumps({'chapter':chapter,'file':str(path),
                  'checks':issues,'draft':saved},ensure_ascii=False),flush=True)
for name in ('writing-metrics.json','narration-metrics.json'):
    path=Path('work/director')/name
    if path.exists(): print('SAVED_METRICS '+json.dumps({'file':name,'data':json.loads(path.read_text())}),flush=True)
if os.getenv('INSPECTION_CHAPTERS_ONLY')=='1':
    raise SystemExit(0)
speech_path=Path('work/director/speech/speech.json')
spoken=json.loads(speech_path.read_text()) if speech_path.exists() else {}
expected_durations={str(s['scene_id']):s['duration'] for s in spoken.get('scenes',[])}
rows=[]
seen=set()
for path in paths:
    value=json.loads(path.read_text())
    programs=value.get('scenes',[]) if 'svg' not in value else [value]
    for original in programs:
        if not isinstance(original,dict) or not isinstance(original.get('svg'),str): continue
        identifier=str(original.get('scene_id'))
        if identifier in expected_durations and abs(original.get('duration',-999)-expected_durations[identifier])>.05:
            continue
        identity=(identifier,original['svg'])
        if identity in seen: continue
        seen.add(identity)
        summary={'file':str(path),'scene_id':original.get('scene_id'),
            'svg_characters':len(original['svg']),'layers':original.get('layers'),
            'events':original.get('events')}
        try:
            validate_scene(original)
            summary['validation']='passed'
        except Exception as exc: summary['validation']=str(exc)
        print('SAVED_PROGRAM '+json.dumps(summary),flush=True)
        safe=re.sub(r'data:image/[^"]+','[embedded approved image]',original['svg'])
        print('SAVED_ARTWORK '+safe[:24000],flush=True)
        save_json(out/(str(len(rows))+'-original.json'),original)
        try:
            program=preview_structure(original)
            validate_scene(program)
            tiles=[]
            for fraction in [.04,.2,.4,.6,.8,.96]:
                frame=scene_frame(program,program['duration']*fraction,(480,270))
                ImageDraw.Draw(frame).text((8,250),str(round(program['duration']*fraction,1))+'s',fill='white',stroke_width=1,stroke_fill='black')
                tiles.append(frame)
            row=Image.new('RGB',(480*len(tiles),270))
            for index,tile in enumerate(tiles): row.paste(tile,(index*480,0))
            rows.append(row)
        except Exception as exc: print('INSPECTION_RENDER_ERROR '+str(exc),flush=True)
        if len(rows)>=4: break
    if len(rows)>=4: break
if rows:
    sheet=Image.new('RGB',(rows[0].width,sum(row.height for row in rows)))
    for index,row in enumerate(rows): sheet.paste(row,(0,index*270))
    sheet.save(out/'saved-scene-temporal.jpg',quality=88)
    encoded=base64.b64encode((out/'saved-scene-temporal.jpg').read_bytes()).decode()
    print('DIRECTOR_IMAGE_START')
    for index in range(0,len(encoded),8000): print('DIRECTOR_IMAGE_CHUNK '+encoded[index:index+8000])
    print('DIRECTOR_IMAGE_END')
