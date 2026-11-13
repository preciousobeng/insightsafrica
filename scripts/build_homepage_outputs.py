"""Dated observation thumbnails, with conservative seasonal matching for NDVI."""

import datetime
import html
import io
import json
import re

from build_homepage_summary import COUNTRIES, atomic
from PIL import Image


def candidates(root, pattern):
    return [
        (code, path, json.loads(path.read_text()))
        for code, config in COUNTRIES.items()
        for path in (root / "data" / config[1]).glob(pattern)
    ]


def svg(title, labels, values, unit, colors):
    maximum = max((v for v in values if v is not None), default=1) or 1
    bars = []
    for i, (label, value) in enumerate(zip(labels, values)):
        x = 56 + i * 128
        height = 0 if value is None else value / maximum * 185
        reading = "N/A" if value is None else f"{value:.1f}{unit}"
        bars.append(
            f'<rect x="{x}" y="{260 - height:.1f}" width="76" height="{height:.1f}" fill="{colors[i % len(colors)]}"/>'
            f'<text x="{x + 38}" y="{244 - height:.1f}" text-anchor="middle">{reading}</text>'
            f'<text x="{x + 38}" y="292" text-anchor="middle">{label}</text>'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 340" width="600" height="340">'
        '<rect width="600" height="340" fill="#F3EEE4"/>'
        '<g fill="#14110D" font-family="monospace" font-size="16">'
        f'<text x="32" y="36">{html.escape(title)}</text>{"".join(bars)}</g></svg>'
    )


def seasonally_comparable(before, after):
    """Same month and <=45 circular days: deliberately stricter than DOY alone.

    A 32-day May/July pair crosses Zamfara's dry-to-wet transition. Matching
    calendar months avoids claiming comparability across that transition.
    Even matched NDVI frames are observations, not attribution of mining impact.
    """
    dates = [datetime.date.fromisoformat(value) for value in (before, after)]
    days = [date.replace(year=2000).timetuple().tm_yday for date in dates]
    distance = abs(days[0] - days[1])
    return dates[0].month == dates[1].month and min(distance, 366 - distance) <= 45


def select_mine(root):
    available = []
    for code, config in COUNTRIES.items():
        folder = root / "data" / config[1]
        path = folder / (
            "galamsey_sites.json" if code == "ghana" else code + "_mining_sites.json"
        )
        if not path.exists():
            continue
        for site in json.loads(path.read_text()):
            dates = re.findall(r"\d{4}-\d{2}-\d{2}", site.get("period", ""))
            name = site.get("ndvi_png")
            if len(dates) != 2 or not name:
                continue
            recent = folder / name
            before = folder / name.replace("_recent_", "_baseline_")
            if not recent.is_file():
                continue
            matched = before.is_file() and seasonally_comparable(*dates)
            available.append((matched, dates[-1], code, site, dates, before, recent))
    if not available:
        raise ValueError("No dated Sentinel-2 frame is available")
    return max(available, key=lambda item: (item[0], item[1], item[2], item[3]["id"]))


def build_outputs(root, pending=None):
    def save(path, content):
        if pending is None:
            atomic(path, content)
        else:
            pending.append((path, content))

    assets = root / "frontend/static/data/homepage-output"
    output = {}
    code, _, obj = max(
        candidates(root, "ndvi_*.json"),
        key=lambda item: (item[2].get("year", 0), item[2].get("doy", 0), item[0]),
    )
    stats = obj["stress_score"]
    date = datetime.date(obj["year"], 1, 1) + datetime.timedelta(days=obj["doy"] - 1)
    save(
        assets / "crop.svg",
        svg(
            "MODIS vegetation health",
            ["Severe", "Moderate", "Fair", "Healthy"],
            [
                stats.get(k)
                for k in ("severe_stress", "moderate_stress", "fair", "healthy")
            ],
            "%",
            ["#8C510A", "#D9A441", "#5AB4AC", "#01665E"],
        ),
    )
    output["crop"] = {
        "country": code,
        "date": date.isoformat(),
        "image": "/static/data/homepage-output/crop.svg",
        "label": COUNTRIES[code][0] + ": vegetation condition",
        "source": "MODIS MOD13Q1",
        "note": "Share of classified pixels; not a crop-yield forecast.",
        "href": f"/{code}/crop/",
    }
    code, _, obj = max(
        candidates(root, "heat_*.json"),
        key=lambda item: (item[2].get("date", ""), item[0], item[2].get("city_id", "")),
    )
    stats = obj["stats"]
    save(
        assets / "heat.svg",
        svg(
            obj["city_name"] + " · land surface",
            ["Minimum", "Mean", "Maximum"],
            [stats.get(k) for k in ("min_lst_c", "mean_lst_c", "max_lst_c")],
            "°C",
            ["#E5B48C", "#CC7952", "#923D26"],
        ),
    )
    output["heat"] = {
        "country": code,
        "date": obj["date"],
        "image": "/static/data/homepage-output/heat.svg",
        "label": obj["city_name"] + ": surface temperature",
        "source": obj["source"],
        "note": "Land-surface temperature is not air temperature.",
        "href": f"/{code}/heat/",
    }
    matched, _, code, site, dates, before, recent = select_mine(root)
    frames = (
        [("before", before), ("after", recent)] if matched else [("single", recent)]
    )
    for label, path in frames:
        with Image.open(path) as image:
            image.thumbnail((760, 440))
            buffer = io.BytesIO()
            image.save(buffer, "WEBP", quality=85)
            save(assets / f"mine-{label}.webp", buffer.getvalue())
    mine = {
        "country": code,
        "site": site["name"],
        "dates": dates if matched else [dates[-1]],
        "mode": "comparison" if matched else "single",
        "source": "Sentinel-2 NDVI",
        "href": f"/{code}/mine/",
    }
    if matched:
        mine.update(
            before="/static/data/homepage-output/mine-before.webp",
            after="/static/data/homepage-output/mine-after.webp",
            note="Same calendar month in different years; vegetation-index observations, not proof of mining impact.",
        )
    else:
        mine.update(
            image="/static/data/homepage-output/mine-single.webp",
            note="One dated vegetation-index frame. No comparable same-season pair is available; this does not show change or attribute mining impact.",
        )
    output["mine"] = mine
    return output
