import json

import numpy as np
import pytest
import soundfile as sf

from history_of_x.core import PipelineError
from history_of_x.director_sound import compose


def test_recorded_score_has_exact_duration_headroom_variation_and_attribution(tmp_path):
    total = compose({}, [{'global_start': 0, 'global_end': 12,
                          'narration_context': 'Ships carried goods between kingdoms.'}], tmp_path)
    music, rate = sf.read(tmp_path / 'music.wav')
    effects, effects_rate = sf.read(tmp_path / 'sfx.wav')
    assert total == 12 and rate == effects_rate == 48000
    assert music.shape == effects.shape == (12 * rate, 2)
    assert .001 < np.sqrt(np.mean(music ** 2)) < .03
    assert np.max(np.abs(music)) <= .121
    # Real recorded stereo material and evolving phrases, not repeated beeps.
    assert np.std(music[:, 0] - music[:, 1]) > .0001
    assert not np.allclose(music[rate:2 * rate], music[5 * rate:6 * rate])
    assert np.count_nonzero(effects) == 0  # No sound on an ordinary cut.
    credits = json.loads((tmp_path / 'music-credits.json').read_text())
    assert credits[0]['artist'] == 'Scott Buckley'
    assert 'CC BY 4.0' in (tmp_path / 'music-credits.txt').read_text()


def test_tragedy_is_silent_and_suppresses_comedy_but_explicit_prop_sound_survives(tmp_path):
    compose({}, [
        {'global_start': 0, 'global_end': 5, 'narration_context': 'A ruler signed the agreement.',
         'events': [{'time': 2, 'sfx': 'paper'}, {'time': 3, 'description': 'A new visual appears.'}]},
        {'global_start': 5, 'global_end': 13, 'narration_context': 'The famine left many victims.',
         'sting': True, 'events': [{'time': 2, 'sfx': 'stamp'}]},
        {'global_start': 13, 'global_end': 20, 'narration_context': 'Rebuilding began.'},
    ], tmp_path)
    music, rate = sf.read(tmp_path / 'music.wav')
    effects, _ = sf.read(tmp_path / 'sfx.wav')
    assert np.count_nonzero(music[5 * rate:13 * rate]) == 0
    assert np.count_nonzero(effects[5 * rate:13 * rate]) == 0
    assert np.max(np.abs(effects[2 * rate:3 * rate])) > .001
    metadata = json.loads((tmp_path / 'soundtrack.json').read_text())
    assert metadata['explicit_sfx'] == [{'at': 2., 'type': 'paper'}]


def test_long_recorded_cue_loops_without_dropouts(tmp_path):
    compose({}, [{'global_start': 0, 'global_end': 78,
                  'narration_context': 'The trade network expanded.'}], tmp_path)
    music, rate = sf.read(tmp_path / 'music.wav')
    # The bundled recording is65s: verify the first loop seam retains signal
    # and introduces no isolated click larger than normal waveform changes.
    seam = music[60 * rate:67 * rate]
    assert np.sqrt(np.mean(seam ** 2)) > .001
    assert np.max(np.abs(np.diff(seam, axis=0))) < .03
    assert len(music) == 78 * rate


@pytest.mark.parametrize('end', [0, -1, float('nan'), float('inf')])
def test_invalid_timeline_is_rejected(tmp_path, end):
    with pytest.raises(PipelineError, match='timeline'):
        compose({}, [{'global_start': 0, 'global_end': end}], tmp_path)
