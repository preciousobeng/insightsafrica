"""
Generate a clean Africa continent SVG path from Natural Earth 110m GeoJSON.
Uses only Python stdlib — no shapely, geopandas, or numpy required.
Outputs a ready-to-paste SVG path element to stdout and writes africa_map.svg.
"""

import urllib.request
import json
import math

# ── Config ──────────────────────────────────────────────────────────────────
GEOJSON_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_110m_admin_0_countries.geojson"
)

# African country ISO A3 codes (all 54 UN-recognised + Western Sahara)
AFRICA_ISO = {
    "DZA","AGO","BEN","BWA","BFA","BDI","CPV","CMR","CAF","TCD",
    "COM","COD","COG","CIV","DJI","EGY","GNQ","ERI","SWZ","ETH",
    "GAB","GMB","GHA","GIN","GNB","KEN","LSO","LBR","LBY","MDG",
    "MWI","MLI","MRT","MUS","MAR","MOZ","NAM","NER","NGA","RWA",
    "STP","SEN","SYC","SLE","SOM","ZAF","SSD","SDN","TZA","TGO",
    "TUN","UGA","ZMB","ZWE","ESH",
}

# SVG viewport
SVG_W = 400
SVG_H = 480
PADDING = 18

# Africa bounding box (lon/lat)
LON_MIN, LON_MAX = -18.0, 52.0
LAT_MIN, LAT_MAX = -35.5, 38.0


def lon_lat_to_xy(lon, lat):
    """Equirectangular projection mapped to SVG space."""
    x = (lon - LON_MIN) / (LON_MAX - LON_MIN) * (SVG_W - 2 * PADDING) + PADDING
    # Invert Y (SVG Y increases downward)
    y = (1 - (lat - LAT_MIN) / (LAT_MAX - LAT_MIN)) * (SVG_H - 2 * PADDING) + PADDING
    return round(x, 2), round(y, 2)


def ring_to_path(ring):
    """Convert a GeoJSON coordinate ring to SVG path commands."""
    parts = []
    for i, (lon, lat) in enumerate(ring):
        x, y = lon_lat_to_xy(lon, lat)
        parts.append(f"{'M' if i == 0 else 'L'}{x},{y}")
    parts.append("Z")
    return " ".join(parts)


def polygon_to_paths(geometry):
    """Handle Polygon and MultiPolygon geometries."""
    paths = []
    if geometry["type"] == "Polygon":
        for ring in geometry["coordinates"]:
            paths.append(ring_to_path(ring))
    elif geometry["type"] == "MultiPolygon":
        for polygon in geometry["coordinates"]:
            for ring in polygon:
                paths.append(ring_to_path(ring))
    return paths


def simplify_ring(ring, tolerance=0.3):
    """
    Ramer-Douglas-Peucker simplification.
    Reduces point count while preserving shape.
    """
    if len(ring) <= 2:
        return ring

    def point_line_dist(p, a, b):
        if a == b:
            return math.hypot(p[0] - a[0], p[1] - a[1])
        dx, dy = b[0] - a[0], b[1] - a[1]
        denom = math.hypot(dx, dy)
        return abs(dy * p[0] - dx * p[1] + b[0] * a[1] - b[1] * a[0]) / denom

    dmax, idx = 0, 0
    for i in range(1, len(ring) - 1):
        d = point_line_dist(ring[i], ring[0], ring[-1])
        if d > dmax:
            dmax, idx = d, i

    if dmax > tolerance:
        left  = simplify_ring(ring[:idx + 1], tolerance)
        right = simplify_ring(ring[idx:], tolerance)
        return left[:-1] + right
    return [ring[0], ring[-1]]


def build_svg(all_paths, ghana_xy):
    gx, gy = ghana_xy
    NL = "\n"

    clip_paths  = NL.join(f'      <path d="{p}"/>' for p in all_paths)
    fill_paths  = NL.join(
        f'  <path d="{p}" fill="url(#af-grad)" stroke="rgba(59,130,246,0.35)" '
        f'stroke-width="0.8" stroke-linejoin="round"/>'
        for p in all_paths
    )
    scan_lines  = NL.join(
        f'    <line x1="0" y1="{y}" x2="{SVG_W}" y2="{y}" stroke="#3b82f6" stroke-width="1"/>'
        for y in range(20, SVG_H, 22)
    )

    # Secondary data dots at rough lon/lat positions
    dot_positions = [
        (32.5,  0.3,  2.0, "rgba(6,182,212,0.5)"),
        (35.0, -1.3,  2.0, "rgba(6,182,212,0.45)"),
        (18.5,  4.4,  1.5, "rgba(34,197,94,0.5)"),
        (28.0, -13.0, 1.5, "rgba(245,158,11,0.45)"),
    ]
    data_dots = NL.join(
        f'  <circle cx="{round(lon_lat_to_xy(lon, lat)[0], 1)}" '
        f'cy="{round(lon_lat_to_xy(lon, lat)[1], 1)}" '
        f'r="{r}" fill="{col}"/>'
        for lon, lat, r, col in dot_positions
    )

    svg = f"""<svg viewBox="0 0 {SVG_W} {SVG_H}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <filter id="af-glow" x="-15%" y="-15%" width="130%" height="130%">
      <feGaussianBlur stdDeviation="2.5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <linearGradient id="af-grad" x1="0%" y1="0%" x2="70%" y2="100%">
      <stop offset="0%" style="stop-color:#1e3a5f"/>
      <stop offset="100%" style="stop-color:#0d1527"/>
    </linearGradient>
    <clipPath id="af-clip">
{clip_paths}
    </clipPath>
  </defs>

  <!-- Country fills -->
{fill_paths}

  <!-- Scan lines clipped to continent -->
  <g clip-path="url(#af-clip)" opacity="0.06">
{scan_lines}
  </g>

  <!-- Ghana pulse marker -->
  <circle cx="{gx}" cy="{gy}" r="4" fill="rgba(59,130,246,0.9)" filter="url(#af-glow)"/>
  <circle cx="{gx}" cy="{gy}" r="4" fill="none" stroke="rgba(59,130,246,0.75)" stroke-width="1.5">
    <animate attributeName="r" from="5" to="18" dur="2.2s" repeatCount="indefinite"/>
    <animate attributeName="opacity" from="0.8" to="0" dur="2.2s" repeatCount="indefinite"/>
  </circle>
  <text x="{gx + 8}" y="{gy - 5}" font-size="8" font-family="monospace" fill="rgba(59,130,246,0.85)">GHA</text>

  <!-- Data dots -->
{data_dots}
</svg>"""
    return svg


def main():
    print("Fetching Natural Earth 110m countries GeoJSON...")
    with urllib.request.urlopen(GEOJSON_URL, timeout=30) as r:
        data = json.loads(r.read().decode())

    print(f"Loaded {len(data['features'])} features, filtering to Africa...")

    all_paths = []
    found = set()

    for feature in data["features"]:
        props = feature.get("properties", {})
        iso = props.get("ADM0_A3") or props.get("ISO_A3") or ""
        if iso not in AFRICA_ISO:
            continue
        found.add(iso)
        geom = feature.get("geometry")
        if not geom:
            continue

        # Simplify and convert each ring
        if geom["type"] == "Polygon":
            rings = [simplify_ring(ring, tolerance=0.35) for ring in geom["coordinates"]]
            geom_simple = {"type": "Polygon", "coordinates": rings}
        elif geom["type"] == "MultiPolygon":
            polys = []
            for poly in geom["coordinates"]:
                polys.append([simplify_ring(ring, tolerance=0.35) for ring in poly])
            geom_simple = {"type": "MultiPolygon", "coordinates": polys}
        else:
            continue

        all_paths.extend(polygon_to_paths(geom_simple))

    missing = AFRICA_ISO - found
    if missing:
        print(f"  Note: {len(missing)} ISO codes not matched (may use different codes): {missing}")
    print(f"  Matched {len(found)} African countries, generated {len(all_paths)} SVG paths")

    # Ghana centroid (approx lon/lat)
    ghana_xy = lon_lat_to_xy(-1.0, 7.95)
    print(f"  Ghana marker at SVG coords: {ghana_xy}")

    svg = build_svg(all_paths, ghana_xy)

    out_path = "scripts/africa_map.svg"
    with open(out_path, "w") as f:
        f.write(svg)
    print(f"\nSVG written to {out_path}")

    # Also print just the path data for easy copy-paste into index.html
    print("\n── Path summary (first 3 paths) ──")
    for p in all_paths[:3]:
        print(p[:120] + "...")
    print(f"\nTotal paths: {len(all_paths)}")
    print("Done. Use scripts/africa_map.svg to inspect, then inline into index.html.")


if __name__ == "__main__":
    main()
