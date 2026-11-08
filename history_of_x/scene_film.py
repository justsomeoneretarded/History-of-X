"""Execute an illustrated scene's explicit layer choreography.

The director supplies artwork and timed transforms. There are no scene templates,
implicit walking cycles, decorative movement, or discarded prose directions.
Coordinates are always a 1920 by 1080 design space. Each top-level SVG group is
rasterized once, then composited at floating point transforms for every frame.
"""
from __future__ import annotations

import copy
import io
import math
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import OrderedDict
from pathlib import Path

import numpy as np
from PIL import Image

from .core import PipelineError, duration, key
from .render import PROFILES

SVG = 'http://www.w3.org/2000/svg'
WIDTH, HEIGHT = 1920, 1080
DEFAULT = dict(x=0., y=0., scale=1., rotation=0., opacity=1., reveal=1.)
EASES = ('linear', 'smooth', 'hold', 'ease_in', 'ease_out')
ALLOWED = {'svg', 'g', 'defs', 'path', 'rect', 'circle', 'ellipse', 'line',
           'polyline', 'polygon', 'text', 'tspan', 'linearGradient',
           'radialGradient', 'stop', 'clipPath', 'mask', 'image', 'title', 'desc',
           'pattern', 'symbol', 'use'}


def schema():
    """Portable structured-output schema for the Gemini scene director."""
    number = {'type': 'number'}
    point = {'type': 'array', 'items': number, 'minItems': 2, 'maxItems': 2}
    kprops = {'time': number, **{name: number for name in DEFAULT},
              'ease': {'type': 'string', 'enum': list(EASES)}}
    frames = {'type': 'array', 'minItems': 1, 'items': {
        'type': 'object', 'required': list(kprops), 'properties': kprops}}
    props = {'id': {'type': 'string'}, 'pivot': point, 'start': number,
             'end': number, 'keyframes': frames,
             'parent': {'type': 'string'}}
    event = {'time': number, 'description': {'type': 'string'},
             'layer_ids': {'type': 'array', 'items': {'type': 'string'}}}
    properties = {
        'scene_id': {'type': 'string'}, 'duration': number,
        'background': {'type': 'string'}, 'svg': {'type': 'string'},
        'layers': {'type': 'array', 'minItems': 1, 'items': {
            'type': 'object', 'required': [p for p in props if p != 'parent'], 'properties': props}},
        'camera': {'type': 'object', 'required': ['keyframes'],
                   'properties': {'keyframes': frames}},
        'events': {'type': 'array', 'items': {
            'type': 'object', 'required': list(event), 'properties': event}},
    }
    return {'type': 'object', 'required': list(properties), 'properties': properties}


def _name(tag):
    return tag.rsplit('}', 1)[-1]


def _svg_tree(source):
    if not isinstance(source, str) or len(source) > 2_000_000:
        raise PipelineError('SVG missing or exceeds 2 MB')
    if re.search(r'<!DOCTYPE|<!ENTITY|<\?xml-stylesheet', source, re.I):
        raise PipelineError('SVG document declarations are disabled')
    try:
        root = ET.fromstring(source)
    except ET.ParseError as exc:
        raise PipelineError(f'Invalid scene SVG: {exc}') from exc
    if _name(root.tag) != 'svg':
        raise PipelineError('Scene artwork needs an SVG root')
    if root.get('viewBox', '').replace(',', ' ').split() != ['0', '0', '1920', '1080']:
        raise PipelineError('Scene SVG viewBox must be 0 0 1920 1080')
    ids = set()
    by_id = {}
    references = []
    count = 0
    for element in root.iter():
        count += 1
        if count > 15000:
            raise PipelineError('Scene SVG exceeds 15000 artwork elements')
        if _name(element.tag) not in ALLOWED:
            raise PipelineError(f'Scene SVG element <{_name(element.tag)}> is unsupported; use paths/shapes rather than filters, CSS or scripted animation')
        identifier = element.get('id')
        if identifier:
            if identifier in ids:
                raise PipelineError('Scene SVG IDs must be unique')
            ids.add(identifier)
            by_id[identifier] = element
        for attr, value in element.attrib.items():
            name = _name(attr).lower()
            if name.startswith('on') or name in {'filter'}:
                raise PipelineError('SVG executable attributes and filters are disabled')
            if name in {'href', 'src'}:
                # Embedded raster assets are intentionally allowed; no URLs/files.
                if not (value.startswith('#') or re.fullmatch(
                        r'data:image/(?:png|jpeg);base64,[A-Za-z0-9+/=\s]+', value)):
                    raise PipelineError('SVG may only reference local IDs or embedded PNG/JPEG')
                if value.startswith('#'):
                    references.append(value[1:])
            for target in re.findall(r'url\(\s*[\"\']?([^\)\"\']+)', value, re.I):
                if not target.startswith('#'):
                    raise PipelineError('External SVG resources are disabled')
                references.append(target[1:])
            if re.search(r'javascript:|@import|expression\(', value, re.I):
                raise PipelineError('Unsafe SVG attribute')
    if any(target not in ids for target in references):
        raise PipelineError('Scene SVG references a missing local definition')
    # Reusable symbols/patterns allow detailed scenery without duplicating markup.
    # Reject recursive or explosively nested <use> trees before rasterization.
    sizes = {}
    def expanded_size(element, ancestors):
        identity = id(element)
        if identity in ancestors:
            raise PipelineError('Scene SVG contains a recursive use reference')
        if identity in sizes:
            return sizes[identity]
        if len(ancestors) > 64:
            raise PipelineError('Scene SVG reusable artwork is nested too deeply')
        next_ancestors = ancestors | {identity}
        size = 1 + sum(expanded_size(child, next_ancestors) for child in element)
        if _name(element.tag) == 'use':
            target = element.get('href') or element.get('{http://www.w3.org/1999/xlink}href') or ''
            if not target.startswith('#'):
                raise PipelineError('SVG use must reference a local artwork ID')
            size += expanded_size(by_id[target[1:]], next_ancestors)
        if size > 60000:
            raise PipelineError('Expanded scene SVG exceeds its artwork complexity limit')
        sizes[identity] = size
        return size
    expanded_size(root, set())
    groups = [child.get('id') for child in root if _name(child.tag) == 'g']
    if not groups or any(not g for g in groups):
        raise PipelineError('Every top-level artwork group requires an ID')
    if any(_name(child.tag) not in {'g', 'defs', 'title', 'desc'} for child in root):
        raise PipelineError('All visible SVG artwork must be inside named top-level groups')
    return root, groups


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _validate_frames(frames, seconds):
    if not isinstance(frames, list) or not 1 <= len(frames) <= 200:
        raise PipelineError('Each layer/camera needs 1–200 keyframes')
    last = -1
    for frame in frames:
        if not isinstance(frame, dict) or not _finite(frame.get('time')):
            raise PipelineError('Keyframes require finite times')
        if not 0 <= frame['time'] <= seconds + .001 or frame['time'] <= last:
            raise PipelineError('Keyframe times must increase within scene duration')
        last = frame['time']
        if set(frame) - {'time', 'ease', *DEFAULT}:
            raise PipelineError('Unknown keyframe channel; refusing to ignore direction')
        if frame.get('ease', 'smooth') not in EASES:
            raise PipelineError('Unsupported keyframe easing')
        for name in DEFAULT:
            value = frame.get(name, DEFAULT[name])
            if not _finite(value):
                raise PipelineError(f'Keyframe {name} must be finite')
            if name in {'opacity', 'reveal'} and not 0 <= value <= 1:
                raise PipelineError(f'Keyframe {name} must be between zero and one')
            if name == 'scale' and not .01 <= value <= 12:
                raise PipelineError('Keyframe scale must be between .01 and 12')
            if name in {'x', 'y'} and abs(value) > 20000:
                raise PipelineError('Keyframe offset exceeds safe scene bounds')


def validate_scene(program):
    if not isinstance(program, dict):
        raise PipelineError('Scene program must be an object')
    required = {'scene_id', 'duration', 'background', 'svg', 'layers', 'camera', 'events'}
    if not required <= program.keys():
        raise PipelineError('Incomplete scene program')
    seconds = program['duration']
    if not _finite(seconds) or not .1 <= seconds <= 180:
        raise PipelineError('Scene duration must be .1–180 seconds')
    if not re.fullmatch(r'#[A-Fa-f0-9]{6}', program['background']):
        raise PipelineError('Scene background must be a six-digit hex color')
    _, groups = _svg_tree(program['svg'])
    layers = program['layers']
    if not isinstance(layers, list) or not 1 <= len(layers) <= 100:
        raise PipelineError('Scene requires 1–100 directed artwork layers')
    ids = [layer.get('id') for layer in layers]
    if len(ids) != len(set(ids)) or set(ids) != set(groups):
        raise PipelineError('Every SVG group must have exactly one directed layer')
    for layer in layers:
        parent = layer.get('parent', '')
        if not isinstance(parent, str) or (parent and parent not in ids):
            raise PipelineError('Layer parent must name an existing layer')
        pivot = layer.get('pivot')
        if not isinstance(pivot, list) or len(pivot) != 2 or not all(_finite(v) for v in pivot):
            raise PipelineError('Layer pivot must be a finite [x,y] coordinate')
        if not all(_finite(layer.get(k)) for k in ('start', 'end')):
            raise PipelineError('Layer needs start/end times')
        if not 0 <= layer['start'] < layer['end'] <= seconds + .001:
            raise PipelineError('Layer lifetime falls outside scene')
        _validate_frames(layer['keyframes'], seconds)
    by_id = {layer['id']: layer for layer in layers}
    for layer in layers:
        ancestry = {layer['id']}
        parent = layer.get('parent', '')
        while parent:
            if parent in ancestry:
                raise PipelineError('Scene layer parent relationships contain a cycle')
            ancestry.add(parent)
            parent = by_id[parent].get('parent', '')
    if not isinstance(program['camera'], dict) or 'keyframes' not in program['camera']:
        raise PipelineError('Scene camera requires keyframes')
    _validate_frames(program['camera']['keyframes'], seconds)
    if not isinstance(program['events'], list):
        raise PipelineError('Scene events must be an array')
    for event in program['events']:
        if not _finite(event.get('time')) or not 0 <= event['time'] <= seconds:
            raise PipelineError('Event falls outside scene')
        if not isinstance(event.get('description'), str) or not event['description'].strip():
            raise PipelineError('Events require a description of a visible consequence')
        if not set(event.get('layer_ids', [])) <= set(ids):
            raise PipelineError('Event references an unknown layer')
    return program


def interpolate(frames, time):
    """Interpolate explicit channels; an omitted channel retains its previous value."""
    poses = []
    previous = dict(DEFAULT)
    for frame in frames:
        previous = {**previous, **{k: frame[k] for k in DEFAULT if k in frame}}
        poses.append({**previous, 'time': frame['time'], 'ease': frame.get('ease', 'smooth')})
    if time <= poses[0]['time']:
        return {k: poses[0][k] for k in DEFAULT}
    for a, b in zip(poses, poses[1:]):
        if time < b['time']:
            u = (time - a['time']) / (b['time'] - a['time'])
            mode = b['ease']
            if mode == 'hold':
                u = 0.
            elif mode == 'smooth':
                u = u*u*(3-2*u)
            elif mode == 'ease_in':
                u = u*u
            elif mode == 'ease_out':
                u = 1-(1-u)**2
            return {k: a[k] + (b[k]-a[k])*u for k in DEFAULT}
    return {k: poses[-1][k] for k in DEFAULT}


def transform_matrix(pose, pivot):
    """Forward artwork-world transform, preserving subpixel translations."""
    radians = math.radians(pose['rotation'])
    a = math.cos(radians)*pose['scale']
    b = math.sin(radians)*pose['scale']
    px, py = pivot
    return np.array([[a, -b, px + pose['x'] - a*px + b*py],
                     [b, a, py + pose['y'] - b*px - a*py],
                     [0., 0., 1.]])


def _raster_layers(program, design_scale=1.):
    try:
        import cairosvg
    except ImportError as exc:
        raise PipelineError('Install CairoSVG to render directed scene artwork') from exc
    root, _ = _svg_tree(program['svg'])
    groups = {child.get('id'): child for child in root if _name(child.tag) == 'g'}
    definitions = [child for child in root if _name(child.tag) == 'defs']
    result = {}
    for layer in program['layers']:
        art = ET.Element(root.tag, dict(root.attrib))
        for definition in definitions:
            art.append(copy.deepcopy(definition))
        art.append(copy.deepcopy(groups[layer['id']]))
        # Sanitization above forbids all network/file references, before CairoSVG.
        png = cairosvg.svg2png(bytestring=ET.tostring(art),
                              output_width=round(WIDTH*design_scale),
                              output_height=round(HEIGHT*design_scale), unsafe=False)
        image = Image.open(io.BytesIO(png)).convert('RGBA')
        bounds = image.getbbox()
        if bounds is None:
            result[layer['id']] = (Image.new('RGBA', (1, 1)), (0., 0.))
        else:
            result[layer['id']] = (image.crop(bounds),
                                   (bounds[0]/design_scale, bounds[1]/design_scale))
    return result


class _PatchCache:
    """Reuse held artwork poses without retaining an unbounded frame history."""
    def __init__(self, pixel_limit=8_000_000):
        self.entries = OrderedDict()
        self.pixels = 0
        self.limit = pixel_limit

    def get(self, identity):
        value = self.entries.get(identity)
        if value is not None:
            self.entries.move_to_end(identity)
        return value

    def put(self, identity, patch, left, top):
        pixels = patch.width*patch.height
        if pixels > self.limit:
            return
        while self.entries and self.pixels+pixels > self.limit:
            _, (old, _, _) = self.entries.popitem(last=False)
            self.pixels -= old.width*old.height
        self.entries[identity] = (patch, left, top)
        self.pixels += pixels


def _composite(canvas, image, offset, matrix, opacity, reveal, design_scale, cache=None):
    if opacity <= 0 or reveal <= 0:
        return
    identity = (id(image), offset, tuple(matrix.flatten()), opacity, reveal, design_scale, canvas.size)
    cached = cache.get(identity) if cache is not None else None
    if cached is not None:
        patch, left, top = cached
        canvas.alpha_composite(patch, (left, top))
        return
    if reveal < 1:
        # The SVG author chooses each route/document as a separate reveal layer.
        image = image.crop((0, 0, max(1, round(image.width*reveal)), image.height))
    if opacity < .9999:
        image = image.copy()
        image.putalpha(image.getchannel('A').point(lambda alpha: round(alpha*opacity)))
    # Convert cropped raster coordinates to design space, then into output pixels.
    local = np.array([[1/design_scale, 0, offset[0]],
                      [0, 1/design_scale, offset[1]], [0, 0, 1]])
    forward = matrix @ local
    corners = forward @ np.array([[0, image.width, image.width, 0],
                                   [0, 0, image.height, image.height], [1, 1, 1, 1]])
    left = max(0, math.floor(corners[0].min())-2)
    top = max(0, math.floor(corners[1].min())-2)
    right = min(canvas.width, math.ceil(corners[0].max())+2)
    bottom = min(canvas.height, math.ceil(corners[1].max())+2)
    if right <= left or bottom <= top:
        return
    inverse = np.linalg.inv(forward) @ np.array([[1, 0, left], [0, 1, top], [0, 0, 1]])
    patch = image.transform((right-left, bottom-top), Image.Transform.AFFINE,
                            tuple(inverse[:2].flatten()),
                            resample=Image.Resampling.BICUBIC)
    if cache is not None:
        cache.put(identity, patch, left, top)
    canvas.alpha_composite(patch, (left, top))


def scene_frame(program, time, size=(960, 540), raster=None, raster_scale=None, cache=None):
    """Render one frame; useful for proof sheets and directed temporal tests."""
    scale = max(size[0]/WIDTH, size[1]/HEIGHT)
    raster_scale = max(1., scale) if raster_scale is None else raster_scale
    raster = raster or _raster_layers(program, raster_scale)
    canvas = Image.new('RGBA', size, program['background'])
    viewport = np.diag([size[0]/WIDTH, size[1]/HEIGHT, 1.])
    camera = interpolate(program['camera']['keyframes'], time)
    camera_matrix = transform_matrix(camera, (WIDTH/2, HEIGHT/2))
    by_id = {layer['id']: layer for layer in program['layers']}
    states = {}
    def state(layer):
        identifier = layer['id']
        if identifier in states:
            return states[identifier]
        pose = interpolate(layer['keyframes'], time)
        matrix = transform_matrix(pose, layer['pivot'])
        opacity = pose['opacity'] if layer['start'] <= time < layer['end'] else 0.
        parent = layer.get('parent', '')
        if parent:
            parent_matrix, parent_opacity, _ = state(by_id[parent])
            matrix = parent_matrix @ matrix
            opacity *= parent_opacity
        states[identifier] = (matrix, opacity, pose['reveal'])
        return states[identifier]
    for layer in program['layers']:
        local, opacity, reveal = state(layer)
        image, offset = raster[layer['id']]
        matrix = viewport @ camera_matrix @ local
        _composite(canvas, image, offset, matrix, opacity*camera['opacity'], reveal, raster_scale, cache)
    return canvas.convert('RGB')


def render_scene(program, directory, profile='cinematic'):
    """Render and cache a silent shot. Invalid scenes fail before creating video."""
    validate_scene(program)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    width, height, fps = PROFILES[profile]
    frames = max(1, round(program['duration']*fps))
    identity = key('directed-svg-film-v1', program, profile)
    target = directory/(identity+'.mp4')
    if target.exists() and abs(duration(target)-frames/fps) < .1:
        return target
    raster_scale = max(1.5 if profile == 'cinematic' else 1., width/WIDTH)
    raster = _raster_layers(program, raster_scale)
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
               '-f', 'rawvideo', '-pixel_format', 'rgb24', '-video_size', f'{width}x{height}',
               '-framerate', str(fps), '-i', '-', '-an', '-c:v', 'libx264',
               '-preset', 'veryfast', '-crf', '19' if profile != 'draft' else '23',
               '-pix_fmt', 'yuv420p', '-threads', '2', '-movflags', '+faststart', str(target)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    cache = _PatchCache()
    try:
        for frame in range(frames):
            process.stdin.write(scene_frame(program, frame/fps, (width, height), raster, raster_scale, cache).tobytes())
        process.stdin.close()
        stderr = process.stderr.read().decode('utf8', errors='replace')
        if process.wait(timeout=120):
            raise PipelineError('Directed scene encoder failed: '+stderr[-1800:])
    except BaseException:
        process.kill()
        process.wait()
        target.unlink(missing_ok=True)
        raise
    return target


def treaty_proof():
    """A small original scene showing a disputed obligation, then rejection.

    This is a renderer proof, not a production fallback or a historical quotation.
    On-screen modal words summarize the dispute rather than reproduce treaty text.
    """
    duration = 15.
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080">
    <defs><linearGradient id="wall" x2="0" y2="1"><stop stop-color="#142A35"/><stop offset="1" stop-color="#234651"/></linearGradient></defs>
    <g id="room"><rect width="1920" height="1080" fill="url(#wall)"/>
    <path d="M0 820H1920V1080H0Z" fill="#10232B"/><path d="M0 820L960 680L1920 820" fill="#315260"/>
    <path d="M100 100H1820V780H100Z M140 140V740H1780V140Z" fill="#AD8A52" fill-rule="evenodd"/>
    <path d="M180 210H1740M180 680H1740" stroke="#78939A" stroke-width="2"/>
    <rect x="200" y="900" width="1520" height="50" rx="20" fill="#AD8A52"/>
    <path d="M240 950V1080M1680 950V1080" stroke="#10232B" stroke-width="50"/></g>
    <g id="heading"><text x="960" y="210" text-anchor="middle" font-family="DejaVu Sans" font-weight="bold" font-size="70" fill="#F3E5CB">ONE TREATY. TWO MEANINGS.</text></g>
    <g id="ethiopian_document"><path d="M310 300H830V850H310Z" fill="#F3E5CB" stroke="#B9975B" stroke-width="8"/>
    <path d="M350 350H790M350 380H620" stroke="#B9975B" stroke-width="8"/>
    <text x="570" y="465" text-anchor="middle" font-family="DejaVu Sans" font-size="40" fill="#183B3D">ETHIOPIAN VERSION</text>
    <text x="570" y="590" text-anchor="middle" font-family="DejaVu Sans" font-weight="bold" font-size="100" fill="#197B6E">MAY</text>
    <text x="570" y="675" text-anchor="middle" font-family="DejaVu Sans" font-size="36" fill="#183B3D">use Italian diplomacy</text>
    <path d="M380 740H760M380 775H690" stroke="#C3B699" stroke-width="8"/></g>
    <g id="italian_document"><path d="M1090 300H1610V850H1090Z" fill="#F3E5CB" stroke="#B9975B" stroke-width="8"/>
    <path d="M1130 350H1570M1130 380H1400" stroke="#B9975B" stroke-width="8"/>
    <text x="1350" y="465" text-anchor="middle" font-family="DejaVu Sans" font-size="40" fill="#183B3D">ITALIAN VERSION</text>
    <text x="1350" y="590" text-anchor="middle" font-family="DejaVu Sans" font-weight="bold" font-size="100" fill="#CA5D48">MUST</text>
    <text x="1350" y="675" text-anchor="middle" font-family="DejaVu Sans" font-size="36" fill="#183B3D">use Italian diplomacy</text>
    <path d="M1160 740H1540M1160 775H1470" stroke="#C3B699" stroke-width="8"/></g>
    <g id="difference"><path d="M850 565H1070M1020 530L1070 565L1020 600" fill="none" stroke="#EAB85C" stroke-width="15" stroke-linecap="round"/></g>
    <g id="refusal"><rect x="1035" y="560" width="630" height="150" rx="12" fill="#9B302A"/><text x="1350" y="663" text-anchor="middle" font-family="DejaVu Sans" font-weight="bold" font-size="84" fill="#FFF2D7">REJECTED</text></g>
    <g id="consequence"><text x="960" y="510" text-anchor="middle" font-family="DejaVu Sans" font-weight="bold" font-size="96" fill="#F3E5CB">SOVEREIGNTY</text><path d="M610 560H1310" stroke="#EAB85C" stroke-width="8"/><text x="960" y="655" text-anchor="middle" font-family="DejaVu Sans" font-size="54" fill="#D2E2DD">The disagreement becomes a confrontation.</text></g>
    </svg>'''
    def frame(t, **changes):
        return {'time': t, **DEFAULT, 'ease': 'smooth', **changes}
    def layer(identifier, frames, start=0., end=duration, pivot=(960, 540)):
        return dict(id=identifier, pivot=list(pivot), start=start, end=end, keyframes=frames)
    return {
        'scene_id': 'treaty-renderer-proof', 'duration': duration, 'background': '#142A35', 'svg': svg,
        'layers': [
            layer('room', [frame(0)]),
            layer('heading', [frame(0, opacity=0), frame(.6), frame(9), frame(10, opacity=0)]),
            layer('ethiopian_document', [frame(0, x=-900), frame(1.3), frame(9), frame(10, x=-1100)], pivot=(570, 575)),
            layer('italian_document', [frame(0, x=900), frame(4, x=900), frame(5.2), frame(9), frame(10, x=1100)], pivot=(1350, 575)),
            layer('difference', [frame(0, reveal=0), frame(5.5, reveal=0), frame(6.5), frame(9), frame(10, opacity=0)]),
            layer('refusal', [frame(0, opacity=0, scale=1.6, rotation=-12), frame(7.8, opacity=0, scale=1.6, rotation=-12), frame(8.1, rotation=-12), frame(9, rotation=-12), frame(10, opacity=0)], pivot=(1350, 635)),
            layer('consequence', [frame(0, opacity=0), frame(10, opacity=0), frame(11)])],
        'camera': {'keyframes': [frame(0), frame(14.9)]},
        'events': [
            {'time': 1.3, 'description': 'The first document presents an optional diplomatic channel.', 'layer_ids': ['ethiopian_document']},
            {'time': 5.2, 'description': 'The second version introduces obligation; the documents can now be compared.', 'layer_ids': ['italian_document']},
            {'time': 6.5, 'description': 'The connecting arrow directs attention to the changed obligation.', 'layer_ids': ['difference']},
            {'time': 8.1, 'description': 'A rejection stamp lands on the compulsory version.', 'layer_ids': ['refusal']},
            {'time': 11, 'description': 'Both documents leave and sovereignty becomes the organizing issue.', 'layer_ids': ['consequence']}],
    }


def acted_treaty_proof():
    """Original 15-second acting test: offer, read, discover, push back, refuse.

    Separate arms, hands, faces, and a shared document have authored keyframes.
    This is an animation capability demonstration, not final historical artwork.
    """
    seconds = 15.
    artwork = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080">
    <defs>
      <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#B8D8D8"/><stop offset="1" stop-color="#F1DEC0"/></linearGradient>
      <linearGradient id="plaster" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#E6CDA8"/><stop offset="1" stop-color="#B99974"/></linearGradient>
      <linearGradient id="robe" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#174E4C"/><stop offset=".6" stop-color="#30726A"/><stop offset="1" stop-color="#113C3D"/></linearGradient>
      <linearGradient id="wood" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#AD7950"/><stop offset="1" stop-color="#65442E"/></linearGradient>
    </defs>
    <g id="architecture">
      <rect width="1920" height="1080" fill="url(#plaster)"/>
      <rect x="0" y="870" width="1920" height="210" fill="#816146"/>
      <path d="M0 870H1920M0 1000H1920M310 870L120 1080M1610 870L1800 1080M960 870V1080" stroke="#5D4634" stroke-width="3"/>
      <path d="M130 680V280Q130 130 300 120Q470 130 470 280V680Z" fill="#654F3B"/>
      <path d="M155 655V285Q155 155 300 145Q445 155 445 285V655Z" fill="url(#sky)"/>
      <path d="M155 510L240 400L310 480L390 370L445 480V655H155Z" fill="#799A84"/>
      <path d="M155 580L260 510L340 555L445 510V655H155Z" fill="#496F63"/>
      <path d="M1450 680V280Q1450 130 1620 120Q1790 130 1790 280V680Z" fill="#654F3B"/>
      <path d="M1475 655V285Q1475 155 1620 145Q1765 155 1765 285V655Z" fill="url(#sky)"/>
      <path d="M1475 520L1560 430L1630 480L1710 400L1765 500V655H1475Z" fill="#799A84"/>
      <path d="M300 150V655M1620 150V655" stroke="#654F3B" stroke-width="10"/>
      <path d="M530 120H1390V160H530Z M540 190H1380V220H540Z" fill="#8A6346"/>
      <path d="M600 280H1320V690H600Z" fill="#D3B087" stroke="#8A6346" stroke-width="5"/>
      <path d="M630 310H1290V660H630Z" fill="#D9BD94" stroke="#E8D5B5" stroke-width="4"/>
      <path d="M680 610L800 410L900 510L1010 360L1180 610Z" fill="#ACAA80"/>
      <path d="M660 610L810 520L920 590L1100 490L1270 610" fill="none" stroke="#87936F" stroke-width="10"/>
      <path d="M0 80H1920M0 105H1920" stroke="#5D4634" stroke-width="18"/>
      <path d="M30 0L210 105M1710 105L1890 0" stroke="#5D4634" stroke-width="25"/>
      <path d="M560 900L960 850L1360 900L1440 1080H480Z" fill="#A34536"/>
      <path d="M600 930L960 880L1320 930L1370 1050H550Z" fill="none" stroke="#D8B56F" stroke-width="8"/>
      <path d="M120 820L70 600L135 550L210 600L230 820Z" fill="#547152"/>
      <path d="M90 630L30 540L100 555L105 450L150 540L210 475L190 580L250 575L200 670" fill="#496544"/>
      <path d="M90 790H230L210 890H110Z" fill="#A86743" stroke="#72452E" stroke-width="5"/>
    </g>
    <g id="left_body">
      <path d="M280 520Q230 580 240 880H590Q605 630 550 525Z" fill="#7A2D30" stroke="#422C2B" stroke-width="7"/>
      <path d="M340 490L490 485L555 900H285Z" fill="url(#robe)" stroke="#193D39" stroke-width="6"/>
      <path d="M360 480L415 570L470 480L460 630L420 680L380 625Z" fill="#EEE1C2"/>
      <path d="M330 510Q420 600 510 505" fill="none" stroke="#D4AE59" stroke-width="10"/>
      <path d="M365 625L460 890M465 625L370 890" stroke="#B28A47" stroke-width="4"/>
      <path d="M320 890L300 980L380 990L410 900M460 900L470 990L550 980L525 890" fill="#27302D" stroke="#172B28" stroke-width="7"/>
      <path d="M300 965L280 995Q320 1010 385 995L380 970M470 970L470 995Q540 1010 570 990L545 965" fill="#352B25"/>
      <ellipse cx="420" cy="370" rx="84" ry="104" fill="#A76F45" stroke="#4B352C" stroke-width="6"/>
      <path d="M337 370Q315 280 370 265Q420 230 470 275Q520 280 500 375L475 340Q420 320 365 340Z" fill="#2C2A25"/>
      <path d="M347 405Q365 505 420 515Q480 505 494 405L470 430L445 425L420 445L390 425L365 430Z" fill="#302E28"/>
      <path d="M370 275Q420 250 470 280" fill="none" stroke="#D9BB73" stroke-width="12"/>
      <circle cx="420" cy="262" r="11" fill="#D9BB73"/>
      <path d="M414 365L405 405L425 407" fill="none" stroke="#6E462F" stroke-width="5"/>
      <path d="M400 439Q420 445 443 437" fill="none" stroke="#CB9C70" stroke-width="4"/>
    </g>
    <g id="left_calm_face"><path d="M366 354L398 350M442 350L474 355" stroke="#2C2A25" stroke-width="8" stroke-linecap="round"/>
      <ellipse cx="385" cy="372" rx="7" ry="9" fill="#241F1B"/><ellipse cx="456" cy="372" rx="7" ry="9" fill="#241F1B"/></g>
    <g id="left_angry_face"><path d="M366 344L400 357M442 357L476 344" stroke="#2C2A25" stroke-width="9" stroke-linecap="round"/>
      <ellipse cx="386" cy="375" rx="8" ry="6" fill="#241F1B"/><ellipse cx="455" cy="375" rx="8" ry="6" fill="#241F1B"/></g>
    <g id="left_reading_arm"><path d="M510 540Q550 580 575 640L680 675" fill="none" stroke="#173B39" stroke-width="62" stroke-linecap="round"/>
      <path d="M510 540Q550 580 575 640L680 675" fill="none" stroke="#33766B" stroke-width="46" stroke-linecap="round"/>
      <path d="M650 663L690 678" stroke="#D8B56F" stroke-width="12"/>
      <path d="M680 675L725 675Q745 680 733 696L680 696Z" fill="#A76F45" stroke="#70482F" stroke-width="4"/></g>
    <g id="right_body">
      <path d="M1390 510Q1330 600 1350 875H1660Q1680 640 1600 510Z" fill="#344B59" stroke="#24333F" stroke-width="7"/>
      <path d="M1450 495L1500 565L1545 495" fill="#E8DAC7" stroke="#24333F" stroke-width="5"/>
      <path d="M1490 548L1510 548L1525 650L1498 680L1475 650Z" fill="#27323D"/>
      <path d="M1360 560L1640 560M1380 585L1620 585" stroke="#A84738" stroke-width="14"/>
      <path d="M1480 680V870M1520 680V870" stroke="#24333F" stroke-width="4"/>
      <circle cx="1478" cy="710" r="6" fill="#D3B45E"/><circle cx="1478" cy="760" r="6" fill="#D3B45E"/><circle cx="1478" cy="810" r="6" fill="#D3B45E"/>
      <path d="M1380 875L1375 980L1465 980L1490 880M1530 880L1550 980L1640 980L1630 875" fill="#293945" stroke="#24333F" stroke-width="7"/>
      <path d="M1375 960L1345 995H1465V970M1550 970V995H1665L1640 960" fill="#342E29"/>
      <ellipse cx="1505" cy="365" rx="80" ry="105" fill="#D3A67E" stroke="#755743" stroke-width="6"/>
      <path d="M1435 335Q1395 285 1450 270Q1480 230 1530 260Q1595 240 1590 335L1565 310Q1505 285 1447 330Z" fill="#68513E"/>
      <path d="M1495 360L1490 400L1515 405" fill="none" stroke="#9D7050" stroke-width="5"/>
      <path d="M1462 423Q1505 395 1548 423L1520 435L1505 425L1480 435Z" fill="#68513E"/>
      <path d="M1478 450H1530" stroke="#8A5C47" stroke-width="5"/>
    </g>
    <g id="right_confident_face"><path d="M1448 340Q1470 330 1485 342M1525 342Q1550 330 1566 342" fill="none" stroke="#68513E" stroke-width="7"/>
      <circle cx="1467" cy="361" r="7" fill="#332B23"/><circle cx="1543" cy="361" r="7" fill="#332B23"/></g>
    <g id="right_surprised_face"><path d="M1448 327L1485 326M1525 326L1566 328" stroke="#68513E" stroke-width="7"/>
      <ellipse cx="1467" cy="356" rx="9" ry="13" fill="#332B23"/><ellipse cx="1543" cy="356" rx="9" ry="13" fill="#332B23"/>
      <ellipse cx="1505" cy="453" rx="14" ry="10" fill="#6F4534"/></g>
    <g id="right_offer_arm"><path d="M1375 550L1300 640L1180 675" fill="none" stroke="#24333F" stroke-width="62" stroke-linecap="round"/>
      <path d="M1375 550L1300 640L1180 675" fill="none" stroke="#344B59" stroke-width="46" stroke-linecap="round"/>
      <path d="M1210 662L1180 681" stroke="#C7A754" stroke-width="12"/>
      <path d="M1180 675L1130 675Q1110 680 1120 696L1180 696Z" fill="#D3A67E" stroke="#9D7050" stroke-width="4"/></g>
    <g id="table"><ellipse cx="960" cy="755" rx="620" ry="105" fill="#4C3426" opacity=".2"/>
      <path d="M330 720L550 645H1380L1600 720L1540 820H380Z" fill="url(#wood)" stroke="#5B3D2B" stroke-width="8"/>
      <path d="M380 820H1540V865H380Z" fill="#5B3D2B"/>
      <path d="M470 850L430 1030H500L550 850M1370 850L1420 1030H1490L1450 850" fill="#5B3D2B"/>
      <path d="M555 660H1370L1540 720H390Z" fill="#BF8C5C" opacity=".5"/>
      <path d="M570 725H1450M540 750H1470" stroke="#91613E" stroke-width="3"/>
      <ellipse cx="1375" cy="680" rx="24" ry="12" fill="#3B3229"/><path d="M1370 680L1400 580L1410 582L1380 682" fill="#DDD1AA"/>
    </g>
    <g id="document"><path d="M850 660L1105 660L1170 765L785 765Z" fill="#F5E8C9" stroke="#C0A271" stroke-width="4"/>
      <path d="M875 688H1080M855 708H1090M840 729H1070" stroke="#A99473" stroke-width="4"/>
      <circle cx="1100" cy="744" r="13" fill="#A64A37"/>
    </g>
    <g id="optional_meaning"><path d="M690 130H1180V280H690Z" fill="#F4E8CB" stroke="#786445" stroke-width="5"/>
      <path d="M815 280L870 320L880 280" fill="#F4E8CB" stroke="#786445" stroke-width="5"/>
      <text x="935" y="225" text-anchor="middle" font-family="DejaVu Sans" font-weight="bold" font-size="64" fill="#27665B">MAY use Rome</text></g>
    <g id="compulsory_meaning"><path d="M690 130H1260V280H690Z" fill="#F4E8CB" stroke="#786445" stroke-width="5"/>
      <path d="M1110 280L1160 320L1170 280" fill="#F4E8CB" stroke="#786445" stroke-width="5"/>
      <text x="975" y="225" text-anchor="middle" font-family="DejaVu Sans" font-weight="bold" font-size="64" fill="#AC4534">MUST use Rome</text></g>
    <g id="refusal_hand"><path d="M490 550L570 455L605 425" fill="none" stroke="#173B39" stroke-width="62" stroke-linecap="round"/>
      <path d="M490 550L570 455L605 425" fill="none" stroke="#33766B" stroke-width="46" stroke-linecap="round"/>
      <path d="M590 445L585 405L590 345Q600 335 605 350L610 393L612 335Q623 325 627 342L628 391L635 345Q648 337 650 352L644 403L658 370Q670 367 670 382L655 430L625 453Z" fill="#A76F45" stroke="#70482F" stroke-width="4"/>
    </g>
    <g id="rejection"><path d="M760 490L1120 450L1140 580L780 620Z" fill="#9E392E" stroke="#F4D5AB" stroke-width="4"/>
      <text x="950" y="552" text-anchor="middle" font-family="DejaVu Sans" font-weight="bold" font-size="62" fill="#FFF1D7">NO DEAL.</text></g>
    </svg>'''
    def k(t, **changes):
        return {'time': t, **DEFAULT, 'ease': 'smooth', **changes}
    def l(name, keys=None, pivot=(960, 540)):
        return {'id': name, 'pivot': list(pivot), 'start': 0., 'end': seconds,
                'keyframes': keys or [k(0), k(seconds)]}
    return {
        'scene_id': 'acted-treaty-proof', 'duration': seconds,
        'background': '#D6BD98', 'svg': artwork,
        'layers': [l('architecture'), l('left_body'),
            l('left_calm_face', [k(0), k(6), k(6.2, opacity=0)]),
            l('left_angry_face', [k(0, opacity=0), k(6, opacity=0), k(6.2)]),
            l('left_reading_arm', [k(0, rotation=12), k(2.7, rotation=12), k(3.5, rotation=-8),
                 k(7.7, rotation=-8), k(8.1, scale=1.25), k(8.6, rotation=8, scale=1.05),
                 k(9.5, rotation=12), k(10.3, opacity=0, rotation=12)], (510, 540)),
            l('right_body'), l('right_confident_face', [k(0), k(8.6), k(8.8, opacity=0)]),
            l('right_surprised_face', [k(0, opacity=0), k(8.6, opacity=0), k(8.8)]),
            l('right_offer_arm', [k(0, rotation=-10), k(.7, rotation=8), k(1.5, rotation=12), k(2.8, rotation=12),
                 k(3.7, rotation=-14), k(8.5, rotation=-14), k(8.9, rotation=-25)], (1375, 550)),
            l('table'),
            l('document', [k(0, x=290), k(1.5, x=-80), k(7.9, x=-80), k(8.1, x=0), k(8.6, x=300), k(15, x=300)]),
            l('optional_meaning', [k(0, opacity=0, y=15), k(3.4, opacity=0, y=15),
                 k(4), k(5.6), k(5.8, opacity=0)]),
            l('compulsory_meaning', [k(0, opacity=0, y=15), k(5.8, opacity=0, y=15), k(6.2),
                 k(7.5), k(8, opacity=0)]),
            l('refusal_hand', [k(0, opacity=0, rotation=25), k(10, opacity=0, rotation=25), k(10.4), k(15)], (490, 550)),
            l('rejection', [k(0, opacity=0, scale=1.4), k(11, opacity=0, scale=1.4), k(11.25), k(15)], (950, 530)),
        ],
        'camera': {'keyframes': [k(0), k(5), k(6.2, scale=1.055), k(10.5, scale=1.055), k(12, scale=1)]},
        'events': [
            {'time': 1.5, 'description': 'The envoy slides the document toward the Ethiopian ruler.', 'layer_ids': ['right_offer_arm', 'document']},
            {'time': 4, 'description': 'The ruler reads an optional diplomatic channel.', 'layer_ids': ['left_reading_arm', 'optional_meaning']},
            {'time': 6.2, 'description': 'An obligation replaces the option and the ruler frowns.', 'layer_ids': ['compulsory_meaning', 'left_angry_face']},
            {'time': 8.6, 'description': 'The ruler pushes the document back; the envoy reacts.', 'layer_ids': ['left_reading_arm', 'document', 'right_surprised_face']},
            {'time': 11.25, 'description': 'The ruler raises a firm refusal hand and the rejection lands.', 'layer_ids': ['refusal_hand', 'rejection']},
        ]}
