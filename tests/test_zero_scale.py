"""Zero-scale reveals must remain invisible without singular-matrix failures."""
from history_of_x.scene_film import scene_frame, validate_scene


def program():
    return {"scene_id":"zero-reveal","duration":4,"background":"#FFFFFF",
            "svg":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080"><g id="actor"><rect x="100" y="100" width="200" height="200" fill="#0033FF"/></g></svg>',
            "layers":[{"id":"actor","pivot":[200,200],"start":0,"end":4,
                       "keyframes":[{"time":0,"scale":0},{"time":2,"scale":1,"ease":"linear"}]}],
            "camera":{"keyframes":[{"time":0}]},"events":[]}


def test_zero_scale_is_hidden_then_reveals_the_authored_artwork():
    source=program()
    validate_scene(source)
    hidden=scene_frame(source,0,size=(1920,1080))
    assert hidden.getpixel((200,200))==(255,255,255)
    shown=scene_frame(source,1,size=(1920,1080))
    assert shown.getpixel((200,200))==(0,51,255)
    assert shown.getpixel((120,120))==(255,255,255)


def test_zero_scale_camera_is_a_hidden_pose_not_a_matrix_error():
    source=program()
    source["layers"][0]["keyframes"]=[{"time":0}]
    source["camera"]["keyframes"]=[{"time":0,"scale":0},{"time":2,"scale":1}]
    validate_scene(source)
    hidden=scene_frame(source,0,size=(1920,1080))
    assert hidden.getpixel((200,200))==(255,255,255)
    shown=scene_frame(source,2,size=(1920,1080))
    assert shown.getpixel((200,200))==(0,51,255)
