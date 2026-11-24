from types import SimpleNamespace
import pytest
from history_of_x.core import PipelineError
from history_of_x.review_media import video_part

class Files:
    def __init__(self,state):self.state=state;self.deleted=[];self.polls=0
    def upload(self,**kwargs):return SimpleNamespace(name='files/test',uri='private-file-uri',state='PROCESSING')
    def get(self,**kwargs):
        self.polls+=1
        return SimpleNamespace(name='files/test',uri='private-file-uri',state=self.state)
    def delete(self,**kwargs):self.deleted.append(kwargs['name'])

class Client:
    def __init__(self,state):self.files=Files(state);self.closed=False
    def close(self):self.closed=True

def test_large_review_waits_for_processing_then_cleans_private_upload(tmp_path):
    path=tmp_path/'review.mp4';path.write_bytes(b'video')
    client=Client('ACTIVE')
    with video_part(None,path,inline_limit=1,client_factory=lambda:client,sleeper=lambda _:None) as part:
        assert 'fileData' in part
        assert client.files.polls==1
        assert not client.closed
    assert client.files.deleted==['files/test']
    assert client.closed

def test_failed_video_processing_cleans_upload_and_rejects_review(tmp_path):
    path=tmp_path/'review.mp4';path.write_bytes(b'video')
    client=Client('FAILED')
    with pytest.raises(PipelineError,match='available'):
        with video_part(None,path,inline_limit=1,client_factory=lambda:client,sleeper=lambda _:None):
            pytest.fail('Unavailable video must never reach the reviewer')
    assert client.files.deleted==['files/test']
    assert client.closed

def test_processing_deadline_does_not_poll_forever(tmp_path):
    path=tmp_path/'review.mp4';path.write_bytes(b'video')
    client=Client('PROCESSING');now=[0.]
    with pytest.raises(PipelineError,match='deadline'):
        with video_part(None,path,inline_limit=1,client_factory=lambda:client,clock=lambda:now[0],sleeper=lambda seconds:now.__setitem__(0,now[0]+seconds),processing_timeout=5):
            pytest.fail('Timed-out video must never reach the reviewer')
    assert now[0]==5
    assert client.files.deleted==['files/test']
    assert client.closed
