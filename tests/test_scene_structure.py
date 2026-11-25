"""Standard SVG root artwork retains paint order and explicit acting."""
import copy
import pytest
from history_of_x.core import PipelineError
from history_of_x.scene_film import normalize_artwork_groups, scene_frame, validate_scene


def program(svg, identifier="actor"):
    return {
        "scene_id":"example", "duration":4, "background":"#FFFFFF", "svg":svg,
        "layers":[{"id":identifier,"pivot":[100,100],"start":0,"end":4,
                   "keyframes":[{"time":0},{"time":4,"x":400,"ease":"linear"}]}],
        "camera":{"keyframes":[{"time":0}]}, "events":[]}


def test_root_background_stays_behind_the_moving_authored_actor():
    source=program('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080">'
                   '<rect width="1920" height="1080" fill="#EEDDCC"/>'
                   '<g id="actor"><rect x="100" y="100" width="200" height="200" fill="#0033FF"/></g></svg>')
    original=copy.deepcopy(source)
    normalized=normalize_artwork_groups(source)
    validate_scene(normalized)
    assert source == original
    assert normalized["layers"][-1] == source["layers"][0]
    frame=scene_frame(normalized,2,size=(1920,1080))
    assert frame.getpixel((350,150)) == (0,51,255)
    assert frame.getpixel((150,150)) == (238,221,204)


def test_a_named_root_shape_keeps_its_existing_authored_keyframes():
    source=program('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080">'
                   '<rect id="actor" x="100" y="100" width="200" height="200" fill="#0033FF"/></svg>')
    normalized=normalize_artwork_groups(source)
    validate_scene(normalized)
    assert normalized["layers"] == source["layers"]
    frame=scene_frame(normalized,2,size=(1920,1080))
    assert frame.getpixel((350,150)) == (0,51,255)
    assert frame.getpixel((150,150)) == (255,255,255)


def test_normalization_does_not_guess_missing_actors_or_accept_external_resources():
    source=program('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080">'
                   '<rect width="1920" height="1080" fill="#EEDDCC"/></svg>')
    with pytest.raises(PipelineError,match="no SVG artwork"):
        normalize_artwork_groups(source)
    source["svg"]=source["svg"].replace('<rect','<image href="https://example.test/private.png"')
    with pytest.raises(PipelineError,match="local IDs"):
        normalize_artwork_groups(source)
