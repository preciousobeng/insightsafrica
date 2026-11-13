"""Build one public homepage snapshot from the local CHIRPS archive; no API calls."""

import argparse
import calendar
import csv
import gzip
import hashlib
import html
import io
import json
import math
import re
import statistics
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COUNTRIES = {
    "ghana": (
        "Ghana",
        "processed",
        "regions",
        "districts",
        "ghana_regions.geojson",
        "Region",
        "District",
    ),
    "nigeria": (
        "Nigeria",
        "processed_nigeria",
        "states",
        "lgas",
        "nigeria_states.geojson",
        "State",
        "LGA",
    ),
    "ivorycoast": (
        "Côte d’Ivoire",
        "processed_ivorycoast",
        "districts",
        "regions",
        "ivorycoast_districts.geojson",
        "District",
        "Region",
    ),
    "senegal": (
        "Senegal",
        "processed_senegal",
        "regions",
        "departments",
        "senegal_regions.geojson",
        "Region",
        "Department",
    ),
    "capeverde": (
        "Cabo Verde",
        "processed_capeverde",
        "islands",
        None,
        "capeverde_islands.geojson",
        "Municipality",
        None,
    ),
    "southafrica": (
        "South Africa",
        "processed_southafrica",
        "provinces",
        "districts",
        "southafrica_provinces.geojson",
        "Province",
        "District",
    ),
}


def number(value):
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError("Rainfall must be finite, non-negative or null")
    return float(value)


def rounded(value):
    return None if value is None else round(value, 1)


def display_name(key):
    name = key.split("|")[0].strip("|")
    return re.sub(r"(?<=[a-zà-öø-ÿ])(?=[A-ZÀ-ÖØ-Þ])", " ", name)


def canonical(key):
    return key.strip("|")


def zonal(obj, level):
    return {canonical(k): v for k, v in obj.get(level, {}).items()}


def area(geometry):
    def ring(points):
        return abs(
            sum(
                math.radians(b[0] - a[0])
                * (2 + math.sin(math.radians(a[1])) + math.sin(math.radians(b[1])))
                for a, b in zip(points, points[1:])
            )
            / 2
        )

    polygons = (
        [geometry["coordinates"]]
        if geometry["type"] == "Polygon"
        else geometry["coordinates"]
    )
    return sum(max(0, ring(p[0]) - sum(ring(h) for h in p[1:])) for p in polygons)


def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8") if isinstance(content, str) else content
    if path.exists() and path.read_bytes() == data:
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        f.write(data)
        temp = Path(f.name)
    try:
        temp.chmod(0o644)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def observed(obj):
    return number(obj.get("mean")) if obj else None


def relative(mm, normal):
    mean = observed(normal)
    sd = normal.get("std") if normal else None
    return [
        rounded(mm),
        rounded((mm / mean - 1) * 100) if mm is not None and mean else None,
        rounded((mm - mean) / sd)
        if mm is not None and mean is not None and sd and sd > 0
        else None,
    ]


def weighted(values, weights):
    pairs = [
        (value, weights[key])
        for key, value in values.items()
        if value is not None and key in weights
    ]
    total = sum(weight for _, weight in pairs)
    return sum(value * weight for value, weight in pairs) / total if total else None


def identity(country, group, key, crosswalk):
    entry = crosswalk.get(country, {}).get(group, {}).get(key, {})
    return entry.get(
        "id",
        country + ":" + hashlib.sha256((group + "|" + key).encode()).hexdigest()[:12],
    ), entry.get("boundary_key", key)


def boundary_path(root, country, config, source, boundary_root):
    if source == "gadm":
        return root / "data" / config[1] / config[4]
    base = boundary_root or root / (
        ".ia-open-boundaries" if source == "geoboundaries" else "data/codab"
    )
    return base / country / (country + "-adm1-mapped.geojson")


def country_summary(
    root, country, config, boundaries="gadm", boundary_root=None, crosswalk=None
):
    crosswalk = crosswalk or {}
    label, processed, primary, secondary, boundary, primary_label, secondary_label = (
        config
    )
    folder = root / "data/archive" / country
    files = sorted((folder / "stats").glob("*.json"))
    if not files:
        raise ValueError(f"{country}: archive is missing")
    baseline = json.loads((folder / f"{country}_ltm_1991_2020.json").read_text())
    if baseline.get("reference_period") != {"start": 1991, "end": 2020}:
        raise ValueError(f"{country}: baseline must be 1991–2020")
    geometry = json.loads(
        boundary_path(root, country, config, boundaries, boundary_root).read_text()
    )
    raw_weights = {
        f["properties"].get("key", f["properties"]["name"]): area(f["geometry"])
        for f in geometry["features"]
    }
    weights = {
        key: raw_weights.get(identity(country, primary, key, crosswalk)[1], 0)
        for key in zonal(json.loads(files[-1].read_text())["zonal_stats"], primary)
    }
    if not all(weight > 0 for weight in weights.values()):
        raise ValueError(f"{country}: boundary/stats join needs a crosswalk")
    months = []
    records = []
    for path in files:
        obj = json.loads(path.read_text())
        year, month = obj["year"], obj["month"]
        if obj.get("country") != country or not 1 <= month <= 12:
            raise ValueError(f"{path}: wrong country/month")
        key = f"{year:04}-{month:02}"
        if (
            months
            and int(key[:4]) * 12 + int(key[5:])
            != int(months[-1][:4]) * 12 + int(months[-1][5:]) + 1
        ):
            raise ValueError(f"{country}: archive gap/duplicate before {key}")
        months.append(key)
        records.append(obj["zonal_stats"])
    if months[0] != "1981-01":
        raise ValueError(f"{country}: archive must start in January 1981")
    last = months[-1]
    month = int(last[5:])
    norms = baseline["months"]
    recent = months[-24:]
    national = []
    for record in records:
        national.append(
            weighted(
                {k: observed(v) for k, v in zonal(record, primary).items()}, weights
            )
        )
    normal = []
    normal_raw = []
    for m in range(1, 13):
        values = [
            value
            for key, value in zip(months, national)
            if 1991 <= int(key[:4]) <= 2020 and int(key[5:]) == m and value is not None
        ]
        if len(values) != 30:
            raise ValueError(
                f"{country}: national normal requires all 30 years for month {m}"
            )
        mean, sd = statistics.mean(values), statistics.pstdev(values)
        normal_raw.append({"mean": mean, "std": sd})
        normal.append([rounded(mean), rounded(sd), len(values)])
    latest = zonal(records[-1], primary)
    primary_norm = zonal(norms[str(month)], primary)
    regions = {}
    for key in weights:
        mm = observed(latest.get(key))
        recent_values = []
        for ym, record in zip(recent, records[-24:]):
            recent_values.append(
                relative(
                    observed(zonal(record, primary).get(key)),
                    zonal(norms[str(int(ym[5:]))], primary).get(key),
                )
            )
        region_id, _ = identity(country, primary, key, crosswalk)
        seasonal = [
            observed(zonal(record, primary).get(key))
            for ym, record in zip(months, records)
            if int(ym[5:]) == month
        ]
        seasonal = [value for value in seasonal if value is not None]
        mean = observed(primary_norm.get(key))
        regions[region_id] = {
            "key": key,
            "name": display_name(key),
            "level": primary_label,
            "normal_mm": rounded(mean),
            "headline_eligible": mean is not None and mean >= 20,
            "rank": 1 + sum(value > mm for value in seasonal)
            if mm is not None
            else None,
            "samples": len(seasonal),
            "value": relative(mm, primary_norm.get(key)),
            "recent": recent_values,
        }
    places = []
    for level, kind in ((primary, primary_label), (secondary, secondary_label)):
        if not level:
            continue
        for key, item in sorted(zonal(records[-1], level).items()):
            mm = observed(item)
            normal_item = zonal(norms[str(month)], level).get(key)
            seasonal = [
                (ym, observed(zonal(record, level).get(key)))
                for ym, record in zip(months, records)
                if int(ym[5:]) == month
            ]
            seasonal = [(ym, value) for ym, value in seasonal if value is not None]
            rank = (
                1 + sum(value > mm for _, value in seasonal) if mm is not None else None
            )
            previous = [
                int(ym[:4])
                for ym, value in seasonal
                if ym < last and mm is not None and value >= mm
            ]
            place_id, _ = identity(country, level, key, crosswalk)
            places.append(
                {
                    "id": place_id,
                    "key": key,
                    "name": display_name(key),
                    "parent": display_name(key.split("|", 1)[1]) if "|" in key else "",
                    "level": kind,
                    "group": level,
                    "value": relative(mm, normal_item),
                    "rank": rank,
                    "samples": len(seasonal),
                    "last_wetter": max(previous) if previous else None,
                    "recent": [
                        rounded(observed(zonal(record, level).get(key)))
                        for record in records[-24:]
                    ],
                }
            )
    recent_values = [
        relative(value, normal_raw[int(ym[5:]) - 1])
        for ym, value in zip(recent, national[-24:])
    ]
    return {
        "name": label,
        "latest": last,
        "value": recent_values[-1],
        "recent_values": recent_values,
        "months": months,
        "national": [rounded(v) for v in national],
        "normal": normal,
        "recent_months": recent,
        "regions": regions,
        "places": places,
    }


def headline_candidate(summary):
    candidates = []
    for code, country in summary["countries"].items():
        for key, region in country["regions"].items():
            value = region["value"]
            if (
                region["headline_eligible"]
                and value[0] is not None
                and value[1] is not None
            ):
                candidates.append((abs(value[1]), code, key))
    return max(candidates) if candidates else None


def headline(summary):
    candidate = headline_candidate(summary)
    if candidate is None:
        return "Explore the latest available rainfall observations."
    _, code, key = candidate
    country = summary["countries"][code]
    region = country["regions"][key]
    mm, pct, _ = region["value"]
    month = calendar.month_name[int(country["latest"][5:])]
    when = f"{month} {country['latest'][:4]}"
    comparison = (
        f"about {1 + pct / 100:.1f}× its {month} normal"
        if pct >= 0
        else f"{abs(pct):g}% below its {month} normal"
    )
    return (
        f"{when}: {region['name']}, {country['name']} received {mm:g} mm, {comparison}; "
        f"rank {region['rank']} of {region['samples']} {month} observations since 1981 (1 = wettest)."
    )


def replace_block(text, key, value):
    start = f"<!-- BEGIN HOMEPAGE:{key} -->"
    end = f"<!-- END HOMEPAGE:{key} -->"
    if (
        text.count(start) != 1
        or text.count(end) != 1
        or text.index(start) > text.index(end)
    ):
        raise ValueError(f"Invalid homepage markers: {key}")
    return re.sub(
        re.escape(start) + ".*?" + re.escape(end),
        lambda _: start + "\n" + value + "\n" + end,
        text,
        flags=re.S,
    )


def fallback_table(summary):
    parts = []
    for code, country in summary["countries"].items():
        years = sorted({ym[:4] for ym in country["months"]})
        rows = {year: [None] * 12 for year in years}
        for ym, value in zip(country["months"], country["national"]):
            rows[ym[:4]][int(ym[5:]) - 1] = value
        parts.append(
            f'<details class="data-table"><summary>{html.escape(country["name"])} monthly national means</summary><div class="table-scroll"><table><caption>Area-weighted administrative mean rainfall (mm)</caption><thead><tr><th scope="col">Year</th>'
            + "".join(
                f'<th scope="col">{calendar.month_abbr[i]}</th>' for i in range(1, 13)
            )
            + "</tr></thead><tbody>"
            + "".join(
                f'<tr><th scope="row">{year}</th>'
                + "".join(
                    f"<td>{'—' if value is None else f'{value:g}'}</td>"
                    for value in values
                )
                + "</tr>"
                for year, values in rows.items()
            )
            + "</tbody></table></div></details>"
        )
    return "\n".join(parts)


def build(
    root=ROOT,
    update_html=True,
    boundaries="gadm",
    boundary_root=None,
    crosswalk=None,
    region_geometry_url=None,
):
    if region_geometry_url and boundaries == "gadm":
        raise ValueError("GADM regional geometry cannot be published (TD-3)")
    summary = {
        "schema": 1,
        "source": {
            "name": "CHIRPS v2.0",
            "url": "https://chc.ucsb.edu/data/chirps",
            "licence": "Public domain",
            "normal": "1991–2020",
            "aggregation": "Area-weighted administrative zonal means; spherical polygon-area weights, excluding missing values.",
        },
        "countries": {},
    }
    for code, config in COUNTRIES.items():
        summary["countries"][code] = country_summary(
            root, code, config, boundaries, boundary_root, crosswalk
        )
    summary["source"]["boundary_weights"] = boundaries
    summary["region_geometry_url"] = region_geometry_url
    dates = {country["latest"] for country in summary["countries"].values()}
    if len(dates) != 1:
        raise ValueError(
            "Countries have different latest months; keep the previous coherent homepage snapshot"
        )
    summary["latest"] = dates.pop()
    summary["headline"] = headline(summary)
    candidate = headline_candidate(summary)
    summary["featured_country"] = (
        candidate[1] if candidate else next(iter(summary["countries"]))
    )
    from build_homepage_outputs import build_outputs

    asset_pending = []
    summary["outputs"] = build_outputs(root, pending=asset_pending)
    text = (
        json.dumps(summary, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        + "\n"
    )
    zipped = gzip.compress(text.encode(), mtime=0)
    if len(zipped) >= 400_000:
        raise ValueError(f"Homepage summary exceeds gzip budget: {len(zipped)} bytes")
    csv_file = io.StringIO()
    writer = csv.writer(csv_file)
    writer.writerow(["country", "month", "rainfall_mm", "method", "source", "licence"])
    for code, country in summary["countries"].items():
        for month, value in zip(country["months"], country["national"]):
            writer.writerow(
                [
                    code,
                    month,
                    "" if value is None else value,
                    "area-weighted administrative mean",
                    "CHIRPS v2.0",
                    "public domain",
                ]
            )
    pending = asset_pending + [
        (root / "frontend/static/data/homepage_summary.json", text),
        (root / "frontend/static/data/homepage_national.csv", csv_file.getvalue()),
    ]
    page = root / "frontend/index.html"
    if update_html:
        current = (root / "frontend/_templates/home.html").read_text()
        lead, separator, rank = summary["headline"].partition("; rank ")
        headline_markup = html.escape(lead)
        if separator:
            headline_markup += (
                f'<span class="headline-rank"> Rank {html.escape(rank)}</span>'
            )
        current = replace_block(current, "headline", headline_markup)
        current = replace_block(current, "tables", fallback_table(summary))
        from homepage_render import latest_table, map_markup, outputs_markup

        current = replace_block(current, "map", map_markup(root, summary))
        current = replace_block(current, "regional_table", latest_table(summary))
        current = replace_block(
            current, "outputs", outputs_markup(root, summary, pending=pending)
        )
        current = replace_block(
            current,
            "flood_link",
            f'<a class="button primary" href="/{summary["featured_country"]}/flood/">Open FloodWatch<span class="sr-only"> for {html.escape(summary["countries"][summary["featured_country"]]["name"])}</span></a>',
        )
        pending.append((page, current))
    for path, content in pending:
        atomic(path, content)
    print(
        f"Homepage summary: {len(text.encode()):,} bytes / {len(zipped):,} gzip; latest {summary['latest']}; "
        + ", ".join(
            f"{c}: {len(v['months'])} months" for c, v in summary["countries"].items()
        )
    )
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--boundaries", choices=("gadm", "geoboundaries", "codab"), default="gadm"
    )
    parser.add_argument("--boundary-root", type=Path)
    parser.add_argument("--crosswalk", type=Path)
    parser.add_argument(
        "--region-geometry-url",
        help="Licensed, separately prepared TopoJSON; forbidden with GADM",
    )
    args = parser.parse_args()
    try:
        build(
            args.root,
            boundaries=args.boundaries,
            boundary_root=args.boundary_root,
            crosswalk=json.loads(args.crosswalk.read_text())
            if args.crosswalk
            else None,
            region_geometry_url=args.region_geometry_url,
        )
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, f"Homepage summary failed: {error}\n")


if __name__ == "__main__":
    main()
