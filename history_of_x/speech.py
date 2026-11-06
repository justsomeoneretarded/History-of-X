from __future__ import annotations
import os
import re
import time
from pathlib import Path
from .core import ROOT, PipelineError, duration, key, save_json, read_json
from .voice_engine import Narrator, speech_check, spoken_form


def clean_words(text):
    return re.findall(r"[\w’'-]+", text.casefold())

def transcript(audio, recognizer):
    segments, _ = recognizer.transcribe(str(audio), language='en', beam_size=3, word_timestamps=True,
        vad_filter=True, condition_on_previous_text=False)
    cues, words = [], []
    for segment in segments:
        cues.append({'start':float(segment.start),'end':float(segment.end),'text':segment.text.strip()})
        for word in segment.words or []:
            words.append({'word':word.word.strip(),'start':float(word.start),'end':float(word.end)})
    return cues, words

def caption_groups(words, maximum=3):
    result, group = [], []
    for word in words:
        # Whisper can return empty/negative/zero duration words. Exclude invalid intervals.
        if not word.get('word','').strip() or word['end']<=word['start']:
            continue
        if group and (len(group)>=maximum or word['start']-group[-1]['end']>.35):
            result.append({'start':group[0]['start'],'end':group[-1]['end'],'text':' '.join(x['word'] for x in group)})
            group=[]
        group.append(word)
        if re.search(r'[.!?;:]$',word['word']):
            result.append({'start':group[0]['start'],'end':group[-1]['end'],'text':' '.join(x['word'] for x in group)})
            group=[]
    if group:
        result.append({'start':group[0]['start'],'end':group[-1]['end'],'text':' '.join(x['word'] for x in group)})
    return result

def align_written(script, words):
    """Map written tokens to ASR timings; preserve names/spelling and monotone timing.

    This is transcript-assisted alignment, not a claim of phoneme-level forced alignment.
    Unmatched spans interpolate only between real ASR anchors, and are reported in QA.
    """
    from difflib import SequenceMatcher
    tokens = script.split()
    left = [re.sub(r'\W','',x.casefold()) for x in tokens]
    right = [re.sub(r'\W','',x['word'].casefold()) for x in words]
    anchors={}
    for block in SequenceMatcher(None,left,right,autojunk=False).get_matching_blocks():
        for i in range(block.size):
            anchors[block.a+i] = words[block.b+i]
    if not words:
        raise PipelineError('Speech recognizer returned no word timings')
    result=[]
    for i, token in enumerate(tokens):
        if i in anchors:
            start,end=anchors[i]['start'],anchors[i]['end']
        else:
            prev=max((j for j in anchors if j<i),default=-1)
            nxt=min((j for j in anchors if j>i),default=len(tokens))
            beginning=anchors[prev]['end'] if prev>=0 else words[0]['start']
            ending=anchors[nxt]['start'] if nxt<len(tokens) else words[-1]['end']
            width=max(.02,(ending-beginning)/max(1,nxt-prev-1))
            start=beginning+(i-prev-1)*width
            end=start+width
        start=max(start,result[-1]['end'] if result else 0)
        result.append({'word':token,'start':start,'end':max(start+.02,end),'interpolated':i not in anchors})
    return result

def produce(script, voice, directory):
    if voice not in ('warguy','kit-laser'):
        raise PipelineError('Choose warguy or kit-laser')
    reference = ROOT/'assets'/'voices'/f'{voice}.ogg'
    if not reference.exists() or not 5<=duration(reference)<=30:
        raise PipelineError('Selected voice reference missing or invalid')
    directory.mkdir(parents=True,exist_ok=True)
    fingerprint=key('speech-v3',voice,reference.read_bytes().hex(),script,os.getenv('VOICE_TAKES','1'))
    index=directory/'speech.json'
    existing=read_json(index) if index.exists() else {'fingerprint':fingerprint,'scenes':[]}
    if existing.get('fingerprint') != fingerprint:
        existing={'fingerprint':fingerprint,'scenes':[]}
    completed={x['scene_id']:x for x in existing['scenes'] if (directory/x['audio']).exists()}
    if len(completed)==len(script['scenes']):
        return existing
    os.environ['TTS_MODEL']='original'
    os.environ.setdefault('VOICE_TAKES','1')
    os.environ.setdefault('TTS_THREADS','2')
    from faster_whisper import WhisperModel
    recognizer=WhisperModel(os.getenv('WHISPER_MODEL','base.en'),device='cpu',compute_type='int8',cpu_threads=2,
        download_root=os.getenv('HF_HOME',str(ROOT/'work'/'models'))+'/whisper')
    narrator=Narrator(reference,directory/'takes')
    try:
        for scene in script['scenes']:
            sid=scene['scene_id']
            if sid in completed:
                continue
            started=time.monotonic()
            for attempt in range(3):
                print(f'Voicing scene {sid}/{len(script["scenes"])} ({voice}), attempt {attempt+1}',flush=True)
                audio=narrator.speak(scene['narration'],attempt_offset=attempt*100003,
                    force=attempt>0,delivery=scene.get('delivery','normal'))
                cues,heard=transcript(audio,recognizer)
                check=speech_check(scene['narration'],cues)
                if check['accepted']:
                    words=align_written(scene['narration'],heard)
                    record={'scene_id':sid,'audio':str(audio.relative_to(directory)), 'duration':duration(audio),
                        'words':words,'captions':caption_groups(words),'verification':check,
                        'generation_seconds':round(time.monotonic()-started,2),
                        'words_per_minute':round(len(scene['narration'].split())*60/duration(audio),1)}
                    completed[sid]=record
                    existing['scenes']=[completed[x['scene_id']] for x in script['scenes'] if x['scene_id'] in completed]
                    existing['voice']=voice
                    save_json(index,existing)
                    break
                print(f'Scene {sid} speech rejected: {check["reason"]}; coverage={check["coverage"]:.2f}',flush=True)
                save_json(directory/f'rejected-{sid}-{attempt}.json',check)
            else:
                raise PipelineError(f'Scene {sid} failed speech verification after 3 attempts. Resume uses all accepted scenes.')
    finally:
        narrator.close()
    return existing
