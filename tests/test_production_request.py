import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('production_request',Path(__file__).parents[1]/'scripts/production_request.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_full_film_requires_reviewed_checkpoint():
    with pytest.raises(ValueError,match='reviewed proof'):
        module.validate({'title':'Ethiopia','brief':'Power across centuries','phase':'film'})

def test_proof_accepts_original_topic_brief():
    config={'title':'Ethiopia','brief':'Power across centuries','phase':'proof'}
    assert module.validate(config)==config

def test_unsupported_model_cannot_silently_change_billing():
    with pytest.raises(ValueError,match='free director'):
        module.validate({'title':'Ethiopia','brief':'Power','director_model':'unverified-paid-model'})
