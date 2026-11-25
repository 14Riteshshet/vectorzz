"""
SookshmaJal – Satellite data module.
Fetches Sentinel-2 L2A data via Planetary Computer STAC,
performs windowed COG reads for bands B04, B05, B08, B11, SCL,
computes NDVI, NDMI, NDRE indices, and falls back to cached JSON
when the API is unreachable.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# ── Lazy imports for heavy geospatial libs ─────────────────────────────────────
try:
    import planetary_computer
    import pystac_client
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds

    _GEOSPATIAL_AVAILABLE = True
except ImportError:
    _GEOSPATIAL_AVAILABLE = False
    logger.warning("Geospatial libs not available – will use fallback cache only.")


# ── Karnataka / Tumakuru STAC search parameters ────────────────────────────────
PC_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-2-l2a"
MAX_CLOUD_COVER = 30  # percent


def _centroid_bbox(
    polygon_coords: list[list[float]], buffer_deg: float = 0.01
) -> tuple[float, float, float, float]:
    """Return (minx, miny, maxx, maxy) bbox around polygon centroid."""
    lons = [c[0] for c in polygon_coords]
    lats = [c[1] for c in polygon_coords]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)
    return (
        min_lon - buffer_deg,
        min_lat - buffer_deg,
        max_lon + buffer_deg,
        max_lat + buffer_deg,
    )


def _centroid(polygon_coords: list[list[float]]) -> tuple[float, float]:
    lons = [c[0] for c in polygon_coords]
    lats = [c[1] for c in polygon_coords]
    return sum(lons) / len(lons), sum(lats) / len(lats)


def _safe_ratio(a: np.ndarray, b: np.ndarray) -> float:
    """Compute mean((a-b)/(a+b)) masking zeros."""
    denom = a.astype(float) + b.astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.where(
            denom != 0, (a.astype(float) - b.astype(float)) / denom, np.nan
        )
    valid = ratio[~np.isnan(ratio)]
    if valid.size == 0:
        return float("nan")
    return float(np.mean(valid))


def _scl_mask(scl: np.ndarray) -> np.ndarray:
    """
    Return boolean mask of valid (non-cloud, non-shadow, non-saturated) pixels.
    SCL classes to keep: 4=Vegetation, 5=Not-vegetated, 6=Water, 11=Snow/Ice excluded
    """
    keep = np.isin(scl, [4, 5, 6])
    return keep


def compute_indices_from_bands(
    b04: np.ndarray,
    b05: np.ndarray,
    b08: np.ndarray,
    b11: np.ndarray,
    scl: np.ndarray | None = None,
) -> dict[str, float]:
    """Compute NDVI, NDMI, NDRE from raw DN arrays. Returns dict of indices."""
    if scl is not None:
        mask = _scl_mask(scl)
        b04 = b04[mask] if mask.any() else b04.flatten()
        b05 = b05[mask] if mask.any() else b05.flatten()
        b08 = b08[mask] if mask.any() else b08.flatten()
        b11 = b11[mask] if mask.any() else b11.flatten()
    else:
        b04 = b04.flatten()
        b05 = b05.flatten()
        b08 = b08.flatten()
        b11 = b11.flatten()

    ndvi = _safe_ratio(b08, b04)  # (NIR - Red) / (NIR + Red)
    ndmi = _safe_ratio(b08, b11)  # (NIR - SWIR) / (NIR + SWIR)
    ndre = _safe_ratio(b08, b05)  # (NIR - RedEdge) / (NIR + RedEdge)

    return {
        "ndvi": round(float(ndvi) if not math.isnan(ndvi) else 0.0, 4),
        "ndmi": round(float(ndmi) if not math.isnan(ndmi) else 0.0, 4),
        "ndre": round(float(ndre) if not math.isnan(ndre) else 0.0, 4),
    }


def _read_band_window(
    href: str,
    bbox: tuple,
    signed_href: str | None = None,
    out_shape: tuple[int, int] = (64, 64),
    is_mask: bool = False,
) -> np.ndarray:
    """Open a COG via rasterio, reproject bbox to raster CRS, and read aligned window."""
    url = signed_href or href
    with rasterio.open(url) as src:
        crs_bbox = transform_bounds("EPSG:4326", src.crs, *bbox) if src.crs else bbox
        window = from_bounds(*crs_bbox, transform=src.transform)
        resampling = Resampling.nearest if is_mask else Resampling.bilinear
        data = src.read(1, window=window, out_shape=out_shape, resampling=resampling)
    return data


def fetch_sentinel2_indices(
    polygon_coords: list[list[float]],
    fallback_cache_dir: str = "fallback_cache",
    taluk_key: str | None = None,
    use_fallback: bool = False,
) -> dict:
    """
    Main entry point. Returns dict with NDVI, NDMI, NDRE, scene_date,
    cloud_cover_pct, data_source.
    Falls back to cached JSON if PC is unreachable, geospatial libs missing,
    or use_fallback=True.
    """
    if not use_fallback and _GEOSPATIAL_AVAILABLE:
        try:
            return _fetch_from_planetary_computer(polygon_coords)
        except Exception as exc:
            logger.warning(
                "Planetary Computer fetch failed (%s), loading fallback.", exc
            )

    return _load_fallback(fallback_cache_dir, taluk_key, polygon_coords)


def _fetch_from_planetary_computer(polygon_coords: list[list[float]]) -> dict:
    """Query STAC, sign assets, read COGs, compute indices."""
    bbox = _centroid_bbox(polygon_coords)
    lon_c, lat_c = _centroid(polygon_coords)

    catalog = pystac_client.Client.open(
        PC_STAC_URL,
        modifier=planetary_computer.sign_inplace,
    )

    search = catalog.search(
        collections=[COLLECTION],
        bbox=bbox,
        query={"eo:cloud_cover": {"lt": MAX_CLOUD_COVER}},
        sortby="-datetime",
        max_items=5,
    )
    items = list(search.items())
    if not items:
        raise RuntimeError("No Sentinel-2 scenes found for this area/date.")

    item = items[0]
    cloud_cover = item.properties.get("eo:cloud_cover", 0.0)
    scene_date = item.datetime.strftime("%Y-%m-%d") if item.datetime else "unknown"

    # Read bands: B04(Red), B05(RedEdge), B08(NIR), B11(SWIR), SCL
    band_map = {"B04": None, "B05": None, "B08": None, "B11": None, "SCL": None}
    for band_name in band_map:
        asset = item.assets.get(band_name)
        if asset is None:
            raise KeyError(f"Band {band_name} not found in Sentinel-2 item assets.")
        band_map[band_name] = _read_band_window(
            asset.href,
            bbox,
            is_mask=(band_name == "SCL"),
        )

    indices = compute_indices_from_bands(
        b04=band_map["B04"],
        b05=band_map["B05"],
        b08=band_map["B08"],
        b11=band_map["B11"],
        scl=band_map["SCL"],
    )
    return {
        **indices,
        "scene_date": scene_date,
        "cloud_cover_pct": round(float(cloud_cover), 2),
        "data_source": "planetary_computer",
    }


def resolve_fallback_cache_path(
    cache_dir: str,
    taluk_key: str | None,
    polygon_coords: list[list[float]],
) -> Path:
    """Resolve the fallback cache JSON path for a Tumakuru taluk or centroid."""
    taluk_map = {
        "madhugiri": "madhugiri_sample.json",
        "koratagere": "koratagere_sample.json",
        "chikkanayakanahalli": "cnhalli_sample.json",
        "cnhalli": "cnhalli_sample.json",
        "c.n.halli": "cnhalli_sample.json",
    }

    filename = None
    if taluk_key:
        filename = taluk_map.get(taluk_key.lower().replace(" ", ""))

    if filename is None:
        # Pick nearest by centroid longitude as a simple heuristic
        lon_c, _ = _centroid(polygon_coords)
        if lon_c < 76.8:
            filename = "cnhalli_sample.json"
        elif lon_c < 77.22:
            filename = "madhugiri_sample.json"
        else:
            filename = "koratagere_sample.json"

    return Path(cache_dir) / filename


def load_taluk_cache(
    cache_dir: str,
    taluk_key: str | None,
    polygon_coords: list[list[float]],
) -> dict | None:
    """Load full pre-cached JSON payload if available, else None."""
    cache_path = resolve_fallback_cache_path(cache_dir, taluk_key, polygon_coords)
    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
        logger.info("Loaded fallback cache from %s", cache_path)
        return data
    return None


def _load_fallback(
    cache_dir: str,
    taluk_key: str | None,
    polygon_coords: list[list[float]],
) -> dict:
    """Load pre-cached satellite indices from JSON files."""
    data = load_taluk_cache(cache_dir, taluk_key, polygon_coords)
    if data is not None:
        return {
            "ndvi": data.get("ndvi", 0.32),
            "ndmi": data.get("ndmi", -0.15),
            "ndre": data.get("ndre", 0.21),
            "scene_date": data.get("scene_date", "2026-10-30"),
            "cloud_cover_pct": data.get("cloud_cover_pct", 5.0),
            "data_source": "fallback_cache",
            "time_series": data.get("time_series"),
        }

    logger.error("Fallback cache file not found in %s", cache_dir)
    # Return synthetic but physically plausible values for Tumakuru dry season
    return {
        "ndvi": 0.28,
        "ndmi": -0.22,
        "ndre": 0.19,
        "scene_date": "2026-10-30",
        "cloud_cover_pct": 0.0,
        "data_source": "synthetic_fallback",
    }
