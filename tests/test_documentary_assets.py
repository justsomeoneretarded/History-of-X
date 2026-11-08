from history_of_x.documentary_assets import bundled_assets, catalog, matching_assets


def test_archive_is_not_misrepresented_as_adwa():
    assets = bundled_assets()
    scene = {"narration": "At Adwa in 1896, Menelik prepared his army.", "asset_search_term": "Adwa 1896"}
    selected = matching_assets(scene, assets, limit=50)
    assert selected
    assert all(item["medium"] != "archival_video" for item in assets if item["id"] in selected)


def test_named_portrait_cannot_stand_in_for_another_emperor():
    assets = bundled_assets()
    selected = matching_assets({"narration": "Haile Selassie addressed the League of Nations."}, assets, limit=50)
    subjects = [item["subject"].casefold() for item in assets if item["id"] in selected]
    assert any("haile selassie" in subject for subject in subjects)
    assert not any("menelik" in subject for subject in subjects)


def test_catalog_is_subject_specific_and_preserves_credits(tmp_path):
    result = catalog({"title": "History of Ethiopia", "scenes": [{"scene_id": 1, "narration": "Coins connected Aksum to trade."}]}, tmp_path, fetch=False)
    assert result["scenes"]["1"]
    for asset in result["assets"]:
        assert all(asset.get(field) for field in ("path", "subject", "date", "license", "source_url", "creator", "context"))
    unrelated = catalog({"title": "History of Japan", "scenes": [{"scene_id": 1, "narration": "Trade expanded."}]}, tmp_path, fetch=False)
    assert unrelated["assets"] == []


def test_generic_country_name_is_not_a_visual_match():
    assert matching_assets({"narration": "Ethiopia changed over the centuries."}, bundled_assets(), limit=50) == []


def test_1935_archive_is_not_used_for_selassies_1974_overthrow():
    assets = bundled_assets()
    selected = matching_assets({"narration": "In 1974 Haile Selassie was overthrown by the Derg."}, assets, limit=50)
    assert selected
    assert all(asset["medium"] != "archival_video" for asset in assets if asset["id"] in selected)
