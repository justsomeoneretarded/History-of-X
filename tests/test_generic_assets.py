"""Museum rights and depiction dates must survive scene-specific discovery."""
from history_of_x.generic_assets import discover, normalize_record, relevant


def met(**changes):
    raw={"objectID":123,"isPublicDomain":True,"primaryImage":"https://images.metmuseum.org/example.jpg",
         "objectURL":"https://www.metmuseum.org/art/collection/search/123",
         "title":"Portrait of Augustus","culture":"Roman","objectDate":"1st century",
         "medium":"Marble","objectName":"Sculpture","objectBeginDate":1,"objectEndDate":100,"tags":[]}
    return {**raw,**changes}


def test_dataset_access_does_not_imply_image_permission():
    assert normalize_record("met",met(isPublicDomain=False)) is None
    assert normalize_record("cleveland",{"id":5,"title":"Roman portrait",
             "share_license_status":"Copyrighted","images":{"web":{"url":"https://example.test/a.jpg"}}}) is None


def test_later_photograph_cannot_become_ancient_event_evidence():
    record=normalize_record("met",met(title="Roman Forum",medium="Gelatin silver photograph",
              objectName="Photograph",objectBeginDate=1901,objectEndDate=1901,objectDate="1901"))
    assert not relevant(record,{"date_label":"100 AD"},"Roman Forum")
    assert relevant(record,{"date_label":"1901"},"Roman Forum")
    assert "not an assumed event date" in record["context"]


def test_country_in_unrelated_bibliography_is_not_subject_identification():
    record=normalize_record("met",met(title="Japanese warrior",culture="Japan",medium="Wood",
                                    objectName="Sculpture",additionalNotes="An exhibition in Rome"))
    assert not relevant(record,{"date_label":"100 AD"},"Roman Augustus")


def test_collection_object_is_not_labeled_as_ancient_live_footage():
    record=normalize_record("met",met())
    assert relevant(record,{"date_label":"1st Century AD"},"Roman Augustus")
    assert record["medium"]=="object_photo"
    assert "not live footage" in record["context"]


def test_discovery_keeps_specific_provenance_and_caches_network_results(tmp_path,monkeypatch):
    from history_of_x import documentary_assets
    raw={"id":42,"share_license_status":"CC0","title":"Bust of Augustus","culture":["Roman"],
         "url":"https://www.clevelandart.org/art/42","creation_date":"First century",
         "creation_date_earliest":1,"creation_date_latest":100,"type":"Sculpture","technique":"Marble",
         "images":{"web":{"url":"https://openaccess-cdn.clevelandart.org/example.jpg"}},"creators":[]}
    class Reply:
        def raise_for_status(self): pass
        def json(self): return {"data":[raw]}
    class Session:
        def __init__(self): self.headers={}; self.calls=0
        def get(self,url,**kwargs):
            self.calls+=1
            return Reply()
    def download(session,url,target):
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists(): target.write_bytes(b"already-verified-image")
        return target
    monkeypatch.setattr(documentary_assets,"_download_image",download)
    session=Session()
    script={"scenes":[{"scene_id":1,"date_label":"100 AD","asset_search_term":"Roman Augustus"}]}
    first=discover(script,tmp_path,session,max_assets=1)
    second=discover(script,tmp_path,session,max_assets=1)
    assert session.calls==1
    assert first["scenes"]["1"]==["cleveland-42"]
    assert second["assets"][0]["source_url"]==raw["url"]
    assert second["assets"][0]["license"]=="CC0 1.0"
    assert second["assets"][0]["sha256"]
    assert not any(k.startswith("_") for k in second["assets"][0])
