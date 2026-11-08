import copy

import pytest

from history_of_x.core import PipelineError
from history_of_x.scene_film import (
    acted_treaty_proof, interpolate, scene_frame, transform_matrix, treaty_proof, validate_scene,
)


def test_treaty_proof_has_visible_causal_changes():
    pytest.importorskip('cairosvg')
    scene = validate_scene(treaty_proof())
    # Physical authored actions, not random differences or a pixel-change threshold:
    # left document present; right arrives; red rejection; both yield to consequence.
    early = scene_frame(scene, 2, (480, 270))
    paired = scene_frame(scene, 6, (480, 270))
    rejected = scene_frame(scene, 8.6, (480, 270))
    conclusion = scene_frame(scene, 12, (480, 270))
    assert early.getpixel((350, 200)) != paired.getpixel((350, 200))
    assert rejected.getpixel((350, 150))[0] > rejected.getpixel((350, 150))[1]
    assert conclusion.getpixel((350, 200)) != paired.getpixel((350, 200))


def test_interpolation_retains_channels_and_honors_hold():
    frames = [{'time': 0, 'x': 10, 'opacity': .5},
              {'time': 2, 'x': 30, 'ease': 'linear'},
              {'time': 4, 'x': 90, 'ease': 'hold'}]
    assert interpolate(frames, 1)['x'] == 20
    assert interpolate(frames, 1)['opacity'] == .5
    assert interpolate(frames, 3)['x'] == 30
    assert interpolate(frames, 4)['x'] == 90


def test_pivot_rotation_and_fractional_position():
    pose = interpolate([{'time': 0, 'x': .125, 'rotation': 90}], 0)
    matrix = transform_matrix(pose, (100, 100))
    assert matrix @ [100, 100, 1] == pytest.approx([100.125, 100, 1])
    assert matrix @ [120, 100, 1] == pytest.approx([100.125, 120, 1])


@pytest.mark.parametrize('injection', [
    '<script>alert(1)</script>',
    '<image href="https://example.com/image.png"/>',
    '<image href="file:///etc/passwd"/>',
    '<rect onclick="alert(1)"/>',
    '<rect fill="url(https://example.com/paint)"/>',
    '<foreignObject/>',
])
def test_svg_rejects_external_or_executable_content(injection):
    scene = treaty_proof()
    scene['svg'] = scene['svg'].replace('</svg>', injection+'</svg>')
    with pytest.raises(PipelineError):
        validate_scene(scene)


def test_unknown_direction_channels_cannot_be_silently_ignored():
    scene = treaty_proof()
    scene['layers'][1]['keyframes'][0]['walk_cycle'] = 5
    with pytest.raises(PipelineError, match='Unknown keyframe'):
        validate_scene(scene)


def test_all_svg_artwork_requires_choreography():
    scene = treaty_proof()
    scene['layers'].pop()
    with pytest.raises(PipelineError, match='Every SVG group'):
        validate_scene(scene)


def test_keyframe_order_and_event_layer_are_validated():
    scene = treaty_proof()
    scene['events'][0]['layer_ids'] = ['unrendered']
    with pytest.raises(PipelineError, match='unknown layer'):
        validate_scene(scene)
    scene = treaty_proof()
    scene['camera']['keyframes'] = [{'time': 2}, {'time': 1}]
    with pytest.raises(PipelineError, match='increase'):
        validate_scene(scene)


def test_parent_rig_moves_child_and_rejects_cycles():
    pytest.importorskip('cairosvg')
    scene = treaty_proof()
    # Link the rejection stamp to the document; its offset should follow that paper.
    stamp = next(l for l in scene['layers'] if l['id'] == 'refusal')
    stamp['parent'] = 'italian_document'
    validate_scene(scene)
    document = next(l for l in scene['layers'] if l['id'] == 'italian_document')
    document['parent'] = 'refusal'
    with pytest.raises(PipelineError, match='cycle'):
        validate_scene(scene)


def test_rendered_child_follows_parent_translation():
    pytest.importorskip('cairosvg')
    scene = treaty_proof()
    scene['svg'] = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080">
      <g id="body"><rect x="0" y="0" width="40" height="40" fill="#0000ff"/></g>
      <g id="hand"><rect x="200" y="200" width="40" height="40" fill="#ff0000"/></g></svg>'''
    scene['background'] = '#ffffff'
    scene['layers'] = [
        {'id': 'body', 'pivot': [0, 0], 'start': 0, 'end': 15, 'keyframes': [{'time': 0, 'x': 400}]},
        {'id': 'hand', 'parent': 'body', 'pivot': [200, 200], 'start': 0, 'end': 15, 'keyframes': [{'time': 0}]},
    ]
    scene['events'] = []
    validate_scene(scene)
    rendered = scene_frame(scene, 1, (480, 270))
    assert rendered.getpixel((155, 55)) == (255, 0, 0)
    assert rendered.getpixel((55, 55)) == (255, 255, 255)


def test_acted_proof_arms_keep_shoulder_contact():
    scene = acted_treaty_proof()
    validate_scene(scene)
    for identifier, shoulder in [('left_reading_arm', (510, 540)), ('right_offer_arm', (1375, 550))]:
        arm = next(layer for layer in scene['layers'] if layer['id'] == identifier)
        for time in [0, 2, 5, 8.1, 8.9, 10]:
            matrix = transform_matrix(interpolate(arm['keyframes'], time), arm['pivot'])
            assert matrix @ [*shoulder, 1] == pytest.approx([*shoulder, 1])
