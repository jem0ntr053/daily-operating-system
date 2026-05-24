import dayctl.persistent as p

def test_load_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "PERSISTENT_PATH", tmp_path / "persistent.json")
    data = p.load_persistent()
    assert data["ideas"] == []
    assert data["settings"]["accent"] == "cyan"
    assert data["settings"]["show_glance"] is True
    assert "ytSubs" in data["stats"]

def test_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "PERSISTENT_PATH", tmp_path / "persistent.json")
    data = p.load_persistent()
    data["ideas"].append({"from": "Music", "text": "idea", "created_at": 1})
    p.save_persistent(data)
    assert p.load_persistent()["ideas"][0]["text"] == "idea"

def test_update_stat_appends_spark_cap_8(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "PERSISTENT_PATH", tmp_path / "persistent.json")
    data = p.load_persistent()
    data["stats"]["ytSubs"]["spark"] = list(range(8))
    p.update_stat(data, "ytSubs", {"v": "12.5K"})
    spark = data["stats"]["ytSubs"]["spark"]
    assert len(spark) == 8 and spark[-1] == 12.5
    assert data["stats"]["ytSubs"]["updated_at"]
