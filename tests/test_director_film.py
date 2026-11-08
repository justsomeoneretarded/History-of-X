"""Integration contracts only; these tests do not certify Gemini art quality."""
import copy

import pytest
from PIL import Image

from history_of_x.core import PipelineError
from history_of_x.director_film import plan_scene
from history_of_x.scene_film import scene_frame, treaty_proof


class SceneAPI:
    def __init__(self, artwork):
        self.artwork = artwork
        self.calls = []

    def vision(self, instruction, payload, images, schema, max_output):
        self.calls.append({'payload': payload, 'images': images})
        return copy.deepcopy(self.artwork)


def inputs(tmp_path, identifier='approved'):
    photo = tmp_path/'photo.jpg'
    Image.new('RGB', (600, 400), '#26bc48').save(photo)
    assets = {'assets': [{'id': 'approved', 'path': str(photo), 'subject': 'An approved subject',
                         'date': '1896', 'context': 'test asset', 'medium': 'historical_photo'}],
              'scenes': {'1': ['approved']}}
    scene = {'scene_id': 1, 'narration': 'A ruler reads and rejects the disputed agreement.'}
    spoken = {'duration': 15., 'words': []}
    program = treaty_proof()
    program['svg'] = program['svg'].replace('<g id="heading">',
        f'<g id="heading"><image href="asset:{identifier}" x="0" y="0" width="600" height="400"/>')
    return scene, spoken, assets, program


def test_director_embeds_only_approved_local_artwork_and_records_usage(tmp_path):
    scene, spoken, assets, artwork = inputs(tmp_path)
    api = SceneAPI(artwork)
    result = plan_scene(api, scene, spoken, assets, tmp_path)
    assert result['asset_ids'] == ['approved']
    assert 'asset:' not in result['svg']
    assert 'data:image/jpeg;base64,' in result['svg']
    assert len(api.calls) == 1
    assert len(api.calls[0]['images']) == 1
    # A cached accepted program must not consume another free-tier request.
    assert plan_scene(api, scene, spoken, assets, tmp_path) == result
    assert len(api.calls) == 1
    pytest.importorskip('cairosvg')
    rendered = scene_frame(result, 1, (480, 270))
    assert rendered.getpixel((30, 30))[1] > 150


def test_unapproved_director_asset_is_rejected_after_bounded_revision(tmp_path):
    scene, spoken, assets, artwork = inputs(tmp_path, 'not-approved')
    api = SceneAPI(artwork)
    with pytest.raises(PipelineError, match='unapproved media asset'):
        plan_scene(api, scene, spoken, assets, tmp_path)
    assert len(api.calls) == 2
    assert 'validation_error' in api.calls[1]['payload']


def test_director_rejects_events_with_large_unexplained_timing_gaps(tmp_path):
    scene, spoken, assets, artwork = inputs(tmp_path)
    artwork['events'] = [{'time': .1, 'description': 'An event.', 'layer_ids': ['room']}]*3
    api = SceneAPI(artwork)
    with pytest.raises(PipelineError, match='meaningful staged developments'):
        plan_scene(api, scene, spoken, assets, tmp_path)
    assert len(api.calls) == 2
