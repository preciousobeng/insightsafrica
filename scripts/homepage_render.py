"""Small data-derived SVG renderers; public maps use Natural Earth only."""

import html
import json
import math

from build_homepage_geography import features

BRBG = ["#8C510A", "#D8B365", "#E3DED4", "#5AB4AC", "#01665E"]
CENTRES = {
    "ghana": (-1.2, 7.8),
    "nigeria": (8.6, 9.5),
    "ivorycoast": (-5.8, 7.6),
    "senegal": (-14.5, 14.5),
    "capeverde": (-24, 16),
    "southafrica": (25, -29),
}
CODES = {
    "ghana": "GH",
    "nigeria": "NG",
    "ivorycoast": "CI",
    "senegal": "SN",
    "capeverde": "CV",
    "southafrica": "ZA",
}


def color(value):
    if value is None:
        return "#A79F93"
    value = max(-50, min(50, value))
    stops = [-50, -25, 0, 25, 50]
    index = min(3, int((value + 50) // 25))
    t = (value - stops[index]) / 25
    a, b = BRBG[index : index + 2]
    rgb = [
        round(int(a[i : i + 2], 16) * (1 - t) + int(b[i : i + 2], 16) * t)
        for i in (1, 3, 5)
    ]
    return "#" + "".join(f"{v:02x}" for v in rgb)


def projection(bounds, box):
    west, south, east, north = bounds
    x, y, width, height = box

    def merc(lat):
        return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))

    scale = min(
        (width - 48) / math.radians(east - west),
        (height - 48) / (merc(north) - merc(south)),
    )
    tx = (
        x + (width - math.radians(east - west) * scale) / 2 - math.radians(west) * scale
    )
    ty = y + (height - (merc(north) - merc(south)) * scale) / 2 + merc(north) * scale
    return lambda point: (
        math.radians(point[0]) * scale + tx,
        ty - merc(point[1]) * scale,
    )


def shape_path(geometry, project):
    polygons = (
        [geometry["coordinates"]]
        if geometry["type"] == "Polygon"
        else geometry["coordinates"]
    )
    return "".join(
        "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in map(project, ring)) + "Z"
        for polygon in polygons
        for ring in polygon
    )


def map_svg(root, summary, mobile=False, thumbnail=False):
    topology = json.loads(
        (root / "frontend/static/data/homepage_countries.topojson").read_text()
    )
    width, height = (720, 660) if mobile else (1100, 650)
    desktop = projection((-27, -36, 54, 38), (0, 0, width, height))
    west = projection((-27, -1, 17, 23), (0, 0, 720, 400))
    south = projection((15, -36, 34, -21), (382, 432, 310, 210))
    project = desktop
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" class="atlas-map {"atlas-map--mobile" if mobile else "atlas-map--desktop"}" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="group" aria-label="Country rainfall departure map, {summary["latest"]}">'
    ]
    if not mobile:
        for feature in features(topology, "africa"):
            parts.append(
                f'<path class="map-context" d="{shape_path(feature["geometry"], project)}"/>'
            )
    else:
        parts.append(
            '<defs><clipPath id="south-inset"><rect x="382" y="432" width="310" height="210"/></clipPath></defs><rect class="inset-frame" x="376" y="406" width="322" height="242"/><text class="inset-label" x="392" y="425">South Africa · separate scale</text>'
        )
    for feature in features(topology, "countries"):
        country = feature["properties"]["country"]
        entry = summary["countries"][country]
        mm, pct, _ = entry["value"]
        if mobile:
            project = south if country == "southafrica" else west
        description = f"{CODES[country]} · {entry['name']}: {'no observation' if mm is None else str(mm) + ' mm'}; {'normal unavailable' if pct is None else str(round(pct + 100, 1)) + '% of normal'}"
        clip = (
            ' clip-path="url(#south-inset)"'
            if mobile and country == "southafrica"
            else ""
        )
        parts.append(
            f'<a class="country-shape" href="/{country}/hub.html" data-country="{country}" aria-label="{html.escape(description)}" title="{html.escape(description)}"{clip}><path fill="{color(pct)}" class="map-fill" d="{shape_path(feature["geometry"], project)}"/>'
        )
        x, y = project(CENTRES[country])
        if country == "capeverde":
            parts.append(
                f'<circle class="map-fill map-marker" fill="{color(pct)}" cx="{x:.1f}" cy="{y:.1f}" r="{10 if mobile else 6}" aria-hidden="true"/>'
            )
        parts.append(
            f'<circle class="map-hit" cx="{x:.1f}" cy="{y:.1f}" r="23"/><text class="map-code" x="{x:.1f}" y="{y:.1f}">{CODES[country]}</text></a>'
        )
    parts.append("</svg>")
    return "".join(parts)


def map_markup(root, summary):
    return map_svg(root, summary) + map_svg(root, summary, True)


def latest_table(summary):
    rows = []
    for code, country in summary["countries"].items():
        for region in country["regions"].values():
            mm, pct, z = region["value"]
            rows.append(
                f'<tr><th scope="row">{html.escape(region["name"])}</th><td>{html.escape(country["name"])}</td><td>{mm if mm is not None else "No data"}</td><td>{round(pct + 100, 1) if pct is not None else "No normal"}</td><td>{z if z is not None else "—"}</td></tr>'
            )
    return (
        '<details class="data-table"><summary>Read the latest regional observations as a table</summary><div class="table-scroll"><table><caption>Latest month '
        + summary["latest"]
        + " · 1991–2020 normal</caption><thead><tr><th>Area</th><th>Country</th><th>Rainfall mm</th><th>% of normal</th><th>z score</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div></details>"
    )


def outputs_markup(root, summary, pending=None):
    outputs = summary["outputs"]
    atomic_image = root / "frontend/static/data/homepage-output/flood.svg"
    from build_homepage_summary import atomic

    thumbnail = map_svg(root, summary).replace(
        "><path",
        "><style>.map-context{fill:#d9cdb9;stroke:#f3eee4;stroke-width:1}.map-fill{stroke:#3d352a;stroke-width:1.8}.map-code{fill:#14110d;font:13px monospace;text-anchor:middle;paint-order:stroke;stroke:#f3eee4;stroke-width:3px}.map-hit{fill:transparent}.map-marker+.map-hit+.map-code{transform:translateY(-14px)}</style><path",
        1,
    )
    if pending is None:
        atomic(atomic_image, thumbnail)
    else:
        pending.append((atomic_image, thumbnail))
    flood = f'<article class="watch-tile"><a href="/{summary["featured_country"]}/flood/"><div class="watch-image"><img src="/static/data/homepage-output/flood.svg" width="600" height="340" loading="lazy" alt="Actual latest national rainfall departures, brown to green"></div><div class="watch-copy"><span class="output-date">{summary["latest"]} · CHIRPS v2.0</span><h3>FloodWatch</h3><p>Where did rain depart from its seasonal normal?</p><span class="text-link">Explore rainfall</span></div></a></article>'
    tiles = [flood]
    for key, title in (("crop", "CropWatch"), ("heat", "HeatWatch")):
        output = outputs[key]
        tiles.append(
            f'<article class="watch-tile"><a href="{output["href"]}"><div class="watch-image"><img src="{output["image"]}" width="600" height="340" loading="lazy" alt="{html.escape(output["label"])}"></div><div class="watch-copy"><span class="output-date">{output["date"]} · {html.escape(output["source"])}</span><h3>{title}</h3><p>{html.escape(output["label"])}. {html.escape(output["note"])}</p><span class="text-link">Explore the observations</span></div></a></article>'
        )
    mine = outputs["mine"]
    if mine["mode"] == "comparison":
        tiles.append(
            f'<article class="watch-tile mine-tile"><div class="compare-images" id="mine-compare"><img class="compare-after" src="{mine["after"]}" width="600" height="340" loading="lazy" alt="Later Sentinel-2 NDVI frame for {html.escape(mine["site"])}"><img class="compare-before" src="{mine["before"]}" width="600" height="340" loading="lazy" alt="Earlier Sentinel-2 NDVI frame for the same site"><span class="compare-label before-label">{mine["dates"][0]}</span><span class="compare-label after-label">{mine["dates"][1]}</span></div><div class="compare-control"><label for="mine-range">Compare earlier and later vegetation</label><input id="mine-range" type="range" min="0" max="100" value="50" aria-label="Sentinel-2 before and after divider"></div><div class="watch-copy"><span class="output-date">Sentinel-2 NDVI · {html.escape(mine["site"])}</span><h3>MineWatch</h3><p>{html.escape(mine["note"])}</p><a class="text-link" href="{mine["href"]}">Explore this site’s observations</a></div></article>'
        )
    else:
        tiles.append(
            f'<article class="watch-tile mine-tile"><div class="watch-image"><img src="{mine["image"]}" width="600" height="340" loading="lazy" alt="Sentinel-2 NDVI observation for {html.escape(mine["site"])}"></div><div class="watch-copy"><span class="output-date">{mine["dates"][0]} · Sentinel-2 NDVI · {html.escape(mine["site"])}</span><h3>MineWatch</h3><p>{html.escape(mine["note"])}</p><a class="text-link" href="{mine["href"]}">Explore this site’s observations</a></div></article>'
        )
    return "".join(tiles)
