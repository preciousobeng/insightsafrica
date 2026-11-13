"""Homepage contracts: data arithmetic, missing observations, licence boundary and update failures."""
import copy
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_homepage_summary as summary
import build_homepage_geography as geography
from scripts import update_all_monthly as updater

CONFIG=("Test","processed","regions","districts","regions.geojson","Region","District")
def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value))
def polygon(west,east):
    return {"type":"Polygon","coordinates":[[[west,0],[east,0],[east,1],[west,1],[west,0]]]}
@pytest.fixture
def archive(tmp_path):
    # Two regions with area weights 1:3 and constant calendar-month baseline.
    write(tmp_path/"data/processed/regions.geojson",{"features":[
        {"properties":{"name":"A"},"geometry":polygon(0,1)},
        {"properties":{"name":"B"},"geometry":polygon(1,4)}]})
    for year in range(1981,2022):
        for month in range(1,13):
            if year==2021 and month>1:break
            values={"A":{"mean":10},"B":{"mean":30}}
            if year==2021:values={"A":{"mean":20},"B":{"mean":40}}
            write(tmp_path/f"data/archive/test/stats/{year}-{month:02}.json",{"country":"test","year":year,"month":month,"zonal_stats":{"regions":values,"districts":{"Town|A":{"mean":None if year==1982 else 20}}}})
    normals={str(m):{"regions":{"A":{"mean":10,"std":2},"B":{"mean":30,"std":5}},"districts":{"Town|A":{"mean":10,"std":2}}} for m in range(1,13)}
    write(tmp_path/"data/archive/test/test_ltm_1991_2020.json",{"reference_period":{"start":1991,"end":2020},"months":normals})
    return tmp_path

def test_national_weighting_and_normal(archive):
    data=summary.country_summary(archive,"test",CONFIG)
    assert len(data["months"])==481
    assert data["national"][-1]==35
    assert data["normal"][0]==[25,0,30]
    assert data["value"]==[35,40,None]
    assert len(data["recent_values"])==24
    assert data["value"]==data["recent_values"][-1]
    regions={r["name"]:r for r in data["regions"].values()}
    assert regions["A"]["value"]==[20,100,5]
    assert regions["B"]["value"]==[40,33.3,2]

def test_missing_is_not_zero_and_ties_share_rank(archive):
    data=summary.country_summary(archive,"test",CONFIG)
    town=next(p for p in data["places"] if p["name"]=="Town")
    assert town["rank"]==1 and town["samples"]==40
    assert town["last_wetter"]==2020
    assert town["parent"]=="A"
    record=archive/"data/archive/test/stats/2021-01.json"
    value=json.loads(record.read_text());value["zonal_stats"]["regions"]["A"]["mean"]=None;write(record,value)
    assert summary.country_summary(archive,"test",CONFIG)["value"][0]==40

@pytest.mark.parametrize("value",[-1,float("nan"),float("inf"),True,"12"])
def test_reject_invalid_rainfall(value):
    with pytest.raises(ValueError):summary.number(value)
def test_zero_normal_is_unavailable():
    assert summary.relative(12,{"mean":0,"std":0})==[12,None,None]
    assert summary.relative(None,{"mean":10,"std":1})==[None,None,None]
    assert summary.relative(0,{"mean":10,"std":1})==[0,-100,-10]

def test_archive_gap_and_wrong_normal_fail(archive):
    record=archive/"data/archive/test/stats/1985-01.json";saved=record.read_bytes();record.unlink()
    with pytest.raises(ValueError,match="gap"):summary.country_summary(archive,"test",CONFIG)
    record.write_bytes(saved)
    path=archive/"data/archive/test/test_ltm_1991_2020.json"
    value=json.loads(path.read_text());value["reference_period"]["start"]=1981;write(path,value)
    with pytest.raises(ValueError,match="baseline"):summary.country_summary(archive,"test",CONFIG)

def test_boundary_source_crosswalk_keeps_identity(archive):
    root=archive/"replacement"
    write(root/"test/test-adm1-mapped.geojson",{"features":[{"properties":{"name":"renamed"},"geometry":polygon(0,1)},{"properties":{"name":"B"},"geometry":polygon(1,4)}]})
    crosswalk={"test":{"regions":{"A":{"id":"test:stable","boundary_key":"renamed"}}}}
    data=summary.country_summary(archive,"test",CONFIG,"geoboundaries",root,crosswalk)
    assert data["regions"]["test:stable"]["key"]=="A"
    assert data["value"][0]==35
    with pytest.raises(ValueError,match="crosswalk"):summary.country_summary(archive,"test",CONFIG,"codab",root)

def test_build_idempotence_and_failed_refresh_keeps_snapshot(archive,monkeypatch):
    import build_homepage_outputs
    monkeypatch.setattr(summary,"COUNTRIES",{"test":CONFIG})
    monkeypatch.setattr(build_homepage_outputs,"build_outputs",lambda root,pending=None:{})
    result=summary.build(archive,update_html=False)
    paths=list((archive/"frontend/static/data").glob("*"))
    before={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in paths}
    summary.build(archive,update_html=False)
    assert before=={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in paths}
    def check(value):
        if isinstance(value,dict):
            assert not {"geometry","coordinates","arcs","bbox"}.intersection(value)
            for v in value.values():check(v)
        elif isinstance(value,list):
            for v in value:check(v)
    check(result)
    (archive/"data/archive/test/stats/1985-01.json").unlink()
    with pytest.raises(ValueError):summary.build(archive,update_html=False)
    assert before=={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in paths}

def test_gadm_publication_guard(archive):
    with pytest.raises(ValueError,match="cannot be published"):
        summary.build(archive,False,region_geometry_url="/static/regions.topojson")
    with pytest.raises(ValueError,match="publicly served"):
        geography.local_regions(archive,output=archive/"frontend/static/regions.topojson")

def test_public_geography_reads_only_natural_earth(tmp_path):
    data=tmp_path/"frontend/static/data"
    source={"type":"FeatureCollection","features":[{"type":"Feature","properties":{"country":"test","name":"Test"},"geometry":polygon(0,1)}]}
    for name in ("africa","covered"):write(data/f"natural-earth-{name}.geojson",source)
    result=geography.public_geometry(tmp_path)
    assert len(result["objects"]["countries"]["geometries"])==1
    ring=geography.features(result,"countries")[0]["geometry"]["coordinates"][0]
    assert sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]))<0

@pytest.mark.parametrize("returncode,expected",[(0,0),(1,1)])
def test_monthly_summary_uses_existing_failure_channel(monkeypatch,returncode,expected):
    monkeypatch.setattr(updater,"newest_release",lambda ceiling:(2026,9))
    monkeypatch.setattr(updater,"update_layers",Mock())
    monkeypatch.setattr(updater,"update_anomaly_archive",Mock())
    runner=Mock(return_value=SimpleNamespace(returncode=returncode,stdout="snapshot ready",stderr="fixture failure"))
    notify=Mock()
    monkeypatch.setattr(updater,"run",runner);monkeypatch.setattr(updater,"notify_failure",notify)
    assert updater.main([])==expected
    assert runner.call_args.args[0][-1].endswith("build_homepage_summary.py")
    assert notify.call_count==expected
def test_monthly_dry_run_writes_nothing(monkeypatch):
    monkeypatch.setattr(updater,"newest_release",lambda ceiling:(2026,9))
    monkeypatch.setattr(updater,"update_layers",Mock())
    monkeypatch.setattr(updater,"update_anomaly_archive",Mock())
    runner=Mock();monkeypatch.setattr(updater,"run",runner)
    assert updater.main(["--dry-run"])==0
    runner.assert_not_called()


def test_public_snapshot_geometry_and_size_contract():
    import gzip
    root=Path(__file__).resolve().parents[1]
    path=root/"frontend/static/data/homepage_summary.json"
    assert len(gzip.compress(path.read_bytes(),mtime=0))<400_000
    data=json.loads(path.read_text())
    assert data["region_geometry_url"] is None
    def inspect(value):
        if isinstance(value,dict):
            assert not {"geometry","coordinates","arcs","bbox"}.intersection(value)
            for child in value.values():inspect(child)
        elif isinstance(value,list):
            for child in value:inspect(child)
    inspect(data)
    topology=json.loads((root/"frontend/static/data/homepage_countries.topojson").read_text())
    assert set(topology["objects"])=={"africa","countries"}
    assert {g["properties"]["country"] for g in topology["objects"]["countries"]["geometries"]}==set(summary.COUNTRIES)

def test_homepage_javascript_budget():
    import gzip
    root=Path(__file__).resolve().parents[1]/"frontend/static"
    files=list(root.glob("homepage*.js"))+[root/"vendor/homepage-vendor.js"]
    assert sum(len(gzip.compress(path.read_bytes(),mtime=0)) for path in files)<150_000

def test_thumbnail_failure_does_not_publish_partial_assets(archive,monkeypatch):
    import build_homepage_outputs
    monkeypatch.setattr(summary,"COUNTRIES",{"test":CONFIG})
    output=archive/"frontend/static/data/homepage-output/crop.svg"
    output.parent.mkdir(parents=True)
    output.write_text("previous asset")
    def fail(root,pending):
        pending.append((output,"new asset"))
        raise ValueError("invalid heat input")
    monkeypatch.setattr(build_homepage_outputs,"build_outputs",fail)
    with pytest.raises(ValueError,match="heat"):summary.build(archive,update_html=False)
    assert output.read_text()=="previous asset"
