"""Homepage contracts: data arithmetic, missing observations, licence boundary and update failures."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_homepage_geography as geography
import build_homepage_summary as summary

from scripts import update_all_monthly as updater

CONFIG = (
    "Test",
    "processed",
    "regions",
    "districts",
    "regions.geojson",
    "Region",
    "District",
)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def polygon(west, east):
    return {
        "type": "Polygon",
        "coordinates": [[[west, 0], [east, 0], [east, 1], [west, 1], [west, 0]]],
    }


@pytest.fixture
def archive(tmp_path):
    # Two regions with area weights 1:3 and constant calendar-month baseline.
    write(
        tmp_path / "data/processed/regions.geojson",
        {
            "features": [
                {"properties": {"name": "A"}, "geometry": polygon(0, 1)},
                {"properties": {"name": "B"}, "geometry": polygon(1, 4)},
            ]
        },
    )
    for year in range(1981, 2022):
        for month in range(1, 13):
            if year == 2021 and month > 1:
                break
            values = {"A": {"mean": 10}, "B": {"mean": 30}}
            if year == 2021:
                values = {"A": {"mean": 20}, "B": {"mean": 40}}
            write(
                tmp_path / f"data/archive/test/stats/{year}-{month:02}.json",
                {
                    "country": "test",
                    "year": year,
                    "month": month,
                    "zonal_stats": {
                        "regions": values,
                        "districts": {"Town|A": {"mean": None if year == 1982 else 20}},
                    },
                },
            )
    normals = {
        str(m): {
            "regions": {"A": {"mean": 10, "std": 2}, "B": {"mean": 30, "std": 5}},
            "districts": {"Town|A": {"mean": 10, "std": 2}},
        }
        for m in range(1, 13)
    }
    write(
        tmp_path / "data/archive/test/test_ltm_1991_2020.json",
        {"reference_period": {"start": 1991, "end": 2020}, "months": normals},
    )
    return tmp_path


def test_national_weighting_and_normal(archive):
    data = summary.country_summary(archive, "test", CONFIG)
    assert len(data["months"]) == 481
    assert data["national"][-1] == 35
    assert data["normal"][0] == [25, 0, 30]
    assert data["value"] == [35, 40, None]
    assert len(data["recent_values"]) == 24
    assert data["value"] == data["recent_values"][-1]
    regions = {r["name"]: r for r in data["regions"].values()}
    assert regions["A"]["value"] == [20, 100, 5]
    assert regions["B"]["value"] == [40, 33.3, 2]


def test_missing_is_not_zero_and_ties_share_rank(archive):
    data = summary.country_summary(archive, "test", CONFIG)
    town = next(p for p in data["places"] if p["name"] == "Town")
    assert town["rank"] == 1 and town["samples"] == 40
    assert town["last_wetter"] == 2020
    assert town["parent"] == "A"
    record = archive / "data/archive/test/stats/2021-01.json"
    value = json.loads(record.read_text())
    value["zonal_stats"]["regions"]["A"]["mean"] = None
    write(record, value)
    assert summary.country_summary(archive, "test", CONFIG)["value"][0] == 40


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, "12"])
def test_reject_invalid_rainfall(value):
    with pytest.raises(ValueError):
        summary.number(value)


def test_zero_normal_is_unavailable():
    assert summary.relative(12, {"mean": 0, "std": 0}) == [12, None, None]
    assert summary.relative(None, {"mean": 10, "std": 1}) == [None, None, None]
    assert summary.relative(0, {"mean": 10, "std": 1}) == [0, -100, -10]


def test_archive_gap_and_wrong_normal_fail(archive):
    record = archive / "data/archive/test/stats/1985-01.json"
    saved = record.read_bytes()
    record.unlink()
    with pytest.raises(ValueError, match="gap"):
        summary.country_summary(archive, "test", CONFIG)
    record.write_bytes(saved)
    path = archive / "data/archive/test/test_ltm_1991_2020.json"
    value = json.loads(path.read_text())
    value["reference_period"]["start"] = 1981
    write(path, value)
    with pytest.raises(ValueError, match="baseline"):
        summary.country_summary(archive, "test", CONFIG)


def test_boundary_source_crosswalk_keeps_identity(archive):
    root = archive / "replacement"
    write(
        root / "test/test-adm1-mapped.geojson",
        {
            "features": [
                {"properties": {"name": "renamed"}, "geometry": polygon(0, 1)},
                {"properties": {"name": "B"}, "geometry": polygon(1, 4)},
            ]
        },
    )
    crosswalk = {
        "test": {"regions": {"A": {"id": "test:stable", "boundary_key": "renamed"}}}
    }
    data = summary.country_summary(
        archive, "test", CONFIG, "geoboundaries", root, crosswalk
    )
    assert data["regions"]["test:stable"]["key"] == "A"
    assert data["value"][0] == 35
    with pytest.raises(ValueError, match="crosswalk"):
        summary.country_summary(archive, "test", CONFIG, "codab", root)


def test_build_idempotence_and_failed_refresh_keeps_snapshot(archive, monkeypatch):
    import build_homepage_outputs

    monkeypatch.setattr(summary, "COUNTRIES", {"test": CONFIG})
    monkeypatch.setattr(
        build_homepage_outputs, "build_outputs", lambda root, pending=None: {}
    )
    result = summary.build(archive, update_html=False)
    paths = list((archive / "frontend/static/data").glob("*"))
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
    summary.build(archive, update_html=False)
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}

    def check(value):
        if isinstance(value, dict):
            assert not {"geometry", "coordinates", "arcs", "bbox"}.intersection(value)
            for v in value.values():
                check(v)
        elif isinstance(value, list):
            for v in value:
                check(v)

    check(result)
    (archive / "data/archive/test/stats/1985-01.json").unlink()
    with pytest.raises(ValueError):
        summary.build(archive, update_html=False)
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}


def test_gadm_publication_guard(archive):
    with pytest.raises(ValueError, match="cannot be published"):
        summary.build(archive, False, region_geometry_url="/static/regions.topojson")
    with pytest.raises(ValueError, match="publicly served"):
        geography.local_regions(
            archive, output=archive / "frontend/static/regions.topojson"
        )


def test_public_geography_reads_only_natural_earth(tmp_path):
    data = tmp_path / "frontend/static/data"
    source = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"country": "test", "name": "Test"},
                "geometry": polygon(0, 1),
            }
        ],
    }
    for name in ("africa", "covered"):
        write(data / f"natural-earth-{name}.geojson", source)
    result = geography.public_geometry(tmp_path)
    assert len(result["objects"]["countries"]["geometries"]) == 1
    ring = geography.features(result, "countries")[0]["geometry"]["coordinates"][0]
    assert sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:])) < 0


@pytest.mark.parametrize("returncode,expected", [(0, 0), (1, 1)])
def test_monthly_summary_uses_existing_failure_channel(
    monkeypatch, returncode, expected
):
    monkeypatch.setattr(updater, "newest_release", lambda ceiling: (2026, 9))
    monkeypatch.setattr(updater, "update_layers", Mock())
    monkeypatch.setattr(updater, "update_anomaly_archive", Mock())
    runner = Mock(
        return_value=SimpleNamespace(
            returncode=returncode, stdout="snapshot ready", stderr="fixture failure"
        )
    )
    notify = Mock()
    monkeypatch.setattr(updater, "run", runner)
    monkeypatch.setattr(updater, "notify_failure", notify)
    assert updater.main([]) == expected
    assert runner.call_args.args[0][-1].endswith("build_homepage_summary.py")
    assert notify.call_count == expected


def test_monthly_dry_run_writes_nothing(monkeypatch):
    monkeypatch.setattr(updater, "newest_release", lambda ceiling: (2026, 9))
    monkeypatch.setattr(updater, "update_layers", Mock())
    monkeypatch.setattr(updater, "update_anomaly_archive", Mock())
    runner = Mock()
    monkeypatch.setattr(updater, "run", runner)
    assert updater.main(["--dry-run"]) == 0
    runner.assert_not_called()


def test_public_snapshot_geometry_and_size_contract(archive, monkeypatch):
    import build_homepage_outputs

    monkeypatch.setattr(summary, "COUNTRIES", {"test": CONFIG})
    monkeypatch.setattr(
        build_homepage_outputs, "build_outputs", lambda root, pending=None: {}
    )
    summary.build(archive, update_html=False)
    import gzip

    root = Path(__file__).resolve().parents[1]
    path = archive / "frontend/static/data/homepage_summary.json"
    assert len(gzip.compress(path.read_bytes(), mtime=0)) < 400_000
    data = json.loads(path.read_text())
    assert data["region_geometry_url"] is None

    def inspect(value):
        if isinstance(value, dict):
            assert not {"geometry", "coordinates", "arcs", "bbox"}.intersection(value)
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    inspect(data)
    topology = json.loads(
        (root / "frontend/static/data/homepage_countries.topojson").read_text()
    )
    assert set(topology["objects"]) == {"africa", "countries"}
    assert {
        g["properties"]["country"]
        for g in topology["objects"]["countries"]["geometries"]
    } == {"ghana", "nigeria", "ivorycoast", "senegal", "capeverde", "southafrica"}


def test_homepage_javascript_budget():
    import gzip

    root = Path(__file__).resolve().parents[1] / "frontend/static"
    files = list(root.glob("homepage*.js")) + [root / "vendor/homepage-vendor.js"]
    assert (
        sum(len(gzip.compress(path.read_bytes(), mtime=0)) for path in files) < 150_000
    )


def test_thumbnail_failure_does_not_publish_partial_assets(archive, monkeypatch):
    import build_homepage_outputs

    monkeypatch.setattr(summary, "COUNTRIES", {"test": CONFIG})
    output = archive / "frontend/static/data/homepage-output/crop.svg"
    output.parent.mkdir(parents=True)
    output.write_text("previous asset")

    def fail(root, pending):
        pending.append((output, "new asset"))
        raise ValueError("invalid heat input")

    monkeypatch.setattr(build_homepage_outputs, "build_outputs", fail)
    with pytest.raises(ValueError, match="heat"):
        summary.build(archive, update_html=False)
    assert output.read_text() == "previous asset"


def headline_region(mm=60, pct=200, normal=20, rank=1, samples=41):
    return {
        "name": "Example",
        "value": [mm, pct, 14.7],
        "normal_mm": normal,
        "headline_eligible": normal >= 20,
        "rank": rank,
        "samples": samples,
        "rank_text": summary.rank_sentence(
            rank, samples, 1981, 2021, "January", pct < 0
        ),
    }


def headline_snapshot(regions):
    return {
        "countries": {"test": {"latest": "2021-01", "name": "Test", "regions": regions}}
    }


def test_headline_excludes_low_baselines_and_keeps_rank():
    data = headline_snapshot(
        {"dry": headline_region(7, 900, 0.7), "wet": headline_region()}
    )
    text = summary.headline(data)
    assert "60 mm, about 3.0× its January normal" in text
    assert "The wettest January in the record (1981–2021)." in text
    assert "900" not in text and "14.7" not in text and "z" not in text


def test_headline_low_baseline_fallback_and_dry_comparison():
    assert (
        summary.headline(headline_snapshot({"dry": headline_region(normal=19.9)}))
        == "Explore the latest available rainfall observations."
    )
    text = summary.headline(
        headline_snapshot({"dry": headline_region(10, -50, 20, 40)})
    )
    assert "10 mm, 50% below its January normal" in text
    assert "Drier than 1 of the 41 Januaries since 1981." in text


@pytest.mark.parametrize(
    "before,after,expected",
    [
        ("2024-05-31", "2026-07-02", False),
        ("2024-07-01", "2026-07-30", True),
        ("2024-02-29", "2025-02-28", True),
        ("2024-01-01", "2026-06-01", False),
    ],
)
def test_mine_seasonal_gate(before, after, expected):
    from build_homepage_outputs import seasonally_comparable

    assert seasonally_comparable(before, after) is expected


def test_mine_uses_single_frame_for_dry_wet_transition(tmp_path, monkeypatch):
    import build_homepage_outputs as outputs

    monkeypatch.setattr(outputs, "COUNTRIES", {"test": CONFIG})
    folder = tmp_path / "data/processed"
    write(
        folder / "test_mining_sites.json",
        [
            {
                "id": "zamfara",
                "name": "Zamfara",
                "period": "2024-05-31 → 2026-07-02",
                "ndvi_png": "site_recent_ndvi.png",
            }
        ],
    )
    (folder / "site_recent_ndvi.png").write_bytes(b"frame")
    (folder / "site_baseline_ndvi.png").write_bytes(b"frame")
    matched, *_ = outputs.select_mine(tmp_path)
    assert matched is False


def test_generated_paths_are_untracked_and_ignored():
    import subprocess

    root = Path(__file__).resolve().parents[1]
    paths = [
        "frontend/index.html",
        "frontend/static/data/homepage_summary.json",
        "frontend/static/data/homepage_national.csv",
        "frontend/static/data/homepage-output/example.svg",
        "evidence/homepage/example.png",
    ]
    assert not subprocess.check_output(["git", "ls-files", "--", *paths], cwd=root)
    for path in paths:
        assert (
            subprocess.run(
                ["git", "check-ignore", "--quiet", path], cwd=root
            ).returncode
            == 0
        )
    assert (root / "frontend/_templates/home.html").is_file()


def test_render_from_template_without_existing_index(archive, monkeypatch):
    import build_homepage_outputs
    import homepage_render

    monkeypatch.setattr(summary, "COUNTRIES", {"test": CONFIG})
    monkeypatch.setattr(
        build_homepage_outputs, "build_outputs", lambda root, pending=None: {}
    )
    monkeypatch.setattr(homepage_render, "map_markup", lambda *args: "<svg>map</svg>")
    monkeypatch.setattr(homepage_render, "latest_table", lambda *args: "table")
    monkeypatch.setattr(
        homepage_render, "outputs_markup", lambda *args, **kwargs: "outputs"
    )
    template = archive / "frontend/_templates/home.html"
    template.parent.mkdir(parents=True)
    template.write_text(
        "\n".join(
            f"<!-- BEGIN HOMEPAGE:{key} --><!-- END HOMEPAGE:{key} -->"
            for key in (
                "headline",
                "tables",
                "map",
                "regional_table",
                "outputs",
                "flood_link",
            )
        )
    )
    summary.build(archive)
    assert "about" in (archive / "frontend/index.html").read_text()
    assert "<svg>map</svg>" in (archive / "frontend/index.html").read_text()


def test_headline_threshold_uses_unrounded_baseline(archive):
    path = archive / "data/archive/test/test_ltm_1991_2020.json"
    value = json.loads(path.read_text())
    value["months"]["1"]["regions"]["A"]["mean"] = 19.99
    value["months"]["1"]["regions"]["B"]["mean"] = 20
    write(path, value)
    data = summary.country_summary(archive, "test", CONFIG)
    regions = {r["name"]: r for r in data["regions"].values()}
    assert regions["A"]["headline_eligible"] is False
    assert regions["B"]["headline_eligible"] is True


def test_repeated_refresh_keeps_git_checkout_clean(archive, monkeypatch):
    import subprocess

    import build_homepage_outputs
    import homepage_render

    monkeypatch.setattr(summary, "COUNTRIES", {"test": CONFIG})
    monkeypatch.setattr(
        build_homepage_outputs, "build_outputs", lambda root, pending=None: {}
    )
    monkeypatch.setattr(homepage_render, "map_markup", lambda *args: "map")
    monkeypatch.setattr(homepage_render, "latest_table", lambda *args: "table")
    monkeypatch.setattr(
        homepage_render, "outputs_markup", lambda *args, **kwargs: "outputs"
    )
    template = archive / "frontend/_templates/home.html"
    template.parent.mkdir(parents=True)
    template.write_text(
        "\n".join(
            f"<!-- BEGIN HOMEPAGE:{key} --><!-- END HOMEPAGE:{key} -->"
            for key in (
                "headline",
                "tables",
                "map",
                "regional_table",
                "outputs",
                "flood_link",
            )
        )
    )
    (archive / ".gitignore").write_text(
        "/data/\n/frontend/index.html\n/frontend/static/data/homepage*\n"
    )

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=archive, text=True)

    git("init", "--quiet")
    git("add", ".gitignore", "frontend/_templates/home.html")
    git(
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "fixture",
    )
    assert git("status", "--porcelain") == ""
    summary.build(archive)
    before = (archive / "frontend/index.html").read_bytes()
    record = archive / "data/archive/test/stats/2021-01.json"
    value = json.loads(record.read_text())
    value["zonal_stats"]["regions"]["B"]["mean"] = 50
    write(record, value)
    summary.build(archive)
    assert (archive / "frontend/index.html").read_bytes() != before
    assert git("status", "--porcelain") == ""


@pytest.mark.parametrize(
    "rank,expected",
    [
        (1, "The wettest September in the record (1981–2026)."),
        (3, "The 3rd-wettest September since 1981."),
        (23, "Wetter than 23 of the 46 Septembers since 1981."),
    ],
)
def test_plain_english_rank_copy(rank, expected):
    assert summary.rank_sentence(rank, 46, 1981, 2026, "September") == expected


def test_tied_rank_one_and_actual_sample_years():
    data = summary.rank_statistics(
        40, [("1983-09", 40), ("1990-09", 20), ("2024-09", 40)], 20, 9
    )
    assert data["rank"] == 1
    assert data["rank_text"] == "The wettest September in the record (1983–2024)."


def test_dry_rank_is_computed_from_observations_not_inverted():
    # Ties make inverted wet rank incorrect: wet rank=3, direct dry rank=1.
    data = summary.rank_statistics(
        10, [("1982-09", 10), ("1995-09", 10), ("2020-09", 20), ("2026-09", 30)], 20, 9
    )
    assert data["rank"] == 3
    assert data["dry_rank"] == 1
    assert data["dry_rank"] != data["samples"] - data["rank"] + 1
    assert data["rank_text"] == "The driest September in the record (1982–2026)."


@pytest.mark.parametrize(
    "rank,expected",
    [
        (3, "The 3rd-driest September since 1981."),
        (23, "Drier than 23 of the 46 Septembers since 1981."),
    ],
)
def test_dry_rank_plain_english(rank, expected):
    assert summary.rank_sentence(rank, 46, 1981, 2026, "September", True) == expected


def test_place_and_region_share_the_same_rank_copy(archive):
    data = summary.country_summary(archive, "test", CONFIG)
    for region in data["regions"].values():
        place = next(
            p
            for p in data["places"]
            if p["group"] == "regions" and p["key"] == region["key"]
        )
        assert place["rank_text"] == region["rank_text"]
        assert (
            place["rank_text"]
            in summary.headline(
                {"countries": {"test": dict(data, regions={place["id"]: region})}}
            )
            or not region["headline_eligible"]
        )
