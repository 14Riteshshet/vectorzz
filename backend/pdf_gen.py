"""
SookshmaJal – ReportLab PDF PMFBY drought-loss dossier generator.
Generates a verifiable PDF with:
  • Plot & farmer details
  • Satellite indices (NDVI, NDMI, NDRE) with interpretation
  • FAO-56 ET₀ and survival water assessment
  • SHA-256 content hash embedded in document
  • QR code linking to /api/verify/{sha256_hash} for tamper-evident ground-truthing
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable,
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    _REPORTLAB_AVAILABLE = True
except ImportError:
    _REPORTLAB_AVAILABLE = False
    logger.warning("ReportLab not available – PDF generation disabled.")

try:
    import qrcode

    _QRCODE_AVAILABLE = True
except ImportError:
    _QRCODE_AVAILABLE = False

# ── Design system colors (from DESIGN.md) ─────────────────────────────────────
COLOR_PRIMARY_TEXT = "#1D1D1F"
COLOR_SECONDARY_TEXT = "#6E6E73"
COLOR_ACCENT_BLUE = "#0066CC"
COLOR_WARNING = "#FF791B"
COLOR_CRITICAL = "#B64400"
COLOR_SURFACE = "#E8E8ED"
COLOR_CARD = "#FFFFFF"


def _hex_to_rl_color(hex_str: str):
    """Convert hex color string to ReportLab Color."""
    if not _REPORTLAB_AVAILABLE:
        return None
    h = hex_str.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return colors.Color(r / 255.0, g / 255.0, b / 255.0)


def _drought_color(stage: str):
    """Return ReportLab Color for drought stage."""
    mapping = {
        "healthy": COLOR_ACCENT_BLUE,
        "early_stress": COLOR_WARNING,
        "moderate_drought": COLOR_WARNING,
        "severe_drought": COLOR_CRITICAL,
    }
    return _hex_to_rl_color(mapping.get(stage, COLOR_ACCENT_BLUE))


def _make_qr_image(url: str, size_mm: float = 40.0) -> Any:
    """Generate QR code image flowable or None."""
    if not (_QRCODE_AVAILABLE and _REPORTLAB_AVAILABLE):
        return None
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        pil_img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        buf.seek(0)
        size = size_mm * mm
        return Image(buf, width=size, height=size)
    except Exception as exc:
        logger.warning("QR generation failed: %s", exc)
        return None


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate_pmfby_pdf(
    payload: dict[str, Any],
    output_dir: str = "generated_pdfs",
    verify_base_url: str = "http://localhost:8000",
) -> tuple[str, str]:
    """
    Generate a PMFBY drought-loss dossier PDF.

    Parameters
    ----------
    payload       : dict containing all analysis fields
    output_dir    : directory to write PDF
    verify_base_url: base URL for QR verification link

    Returns
    -------
    (pdf_path, sha256_hash) tuple
    """
    if not _REPORTLAB_AVAILABLE:
        raise RuntimeError("ReportLab is not installed. Cannot generate PDF.")

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # ── Extract fields ──────────────────────────────────────────────────────
    farmer = payload.get("farmer_name", "Unknown")
    phone = payload.get("phone_number")
    crop = payload.get("crop_type", "Unknown")
    district = payload.get("district") or "Tumakuru"
    taluk = payload.get("taluk", "Unknown")
    hobli = payload.get("hobli")
    village = payload.get("village")
    survey_no = payload.get("survey_no")
    area = payload.get("area_acres", 0.0)
    irrigation_source = payload.get("irrigation_source")
    observed_symptoms = payload.get("observed_symptoms") or []
    pmfby_eligible = payload.get("pmfby_eligible")
    photo_sha256 = payload.get("photo_sha256")
    photo_lat = payload.get("photo_lat")
    photo_lon = payload.get("photo_lon")
    photo_timestamp = payload.get("photo_timestamp")
    photo_path = payload.get("photo_path")
    geolock_status = payload.get("geolock_status", "MISSING_GPS")
    region_match = payload.get("region_match", False)
    distance_km = payload.get("distance_km")
    plot_id = payload.get("plot_id", "N/A")
    lat = payload.get("centroid_lat", 0.0)
    lon = payload.get("centroid_lon", 0.0)

    sat = payload.get("satellite", {})
    ndvi = sat.get("ndvi", 0.0)
    ndmi = sat.get("ndmi", 0.0)
    ndre = sat.get("ndre", 0.0)
    scene_date = sat.get("scene_date", "N/A")
    cloud_cover = sat.get("cloud_cover_pct", 0.0)
    data_source = sat.get("data_source", "N/A")

    drought = payload.get("drought", {})
    drought_stage = drought.get("stage", "unknown")
    stage_label = drought.get("stage_label", "Unknown")
    rec_en = drought.get("recommendation_en", "")

    hydromet = payload.get("hydromet", {})
    et0 = hydromet.get("et0_mm_day", 0.0)
    precip = hydromet.get("precipitation_mm", 0.0)
    soil_m = hydromet.get("soil_moisture_0_7cm_pct", 0.0)
    v_surv = hydromet.get("survival_liters", 0.0)
    deficit = hydromet.get("deficit_mm", 0.0)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── Build PDF ──────────────────────────────────────────────────────────
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"PMFBY Dossier – {farmer}",
        author="SookshmaJal – Team VECTORZZ",
        subject="Drought Loss Ground-Truth Dossier",
    )

    styles = getSampleStyleSheet()
    c_primary = _hex_to_rl_color(COLOR_PRIMARY_TEXT)
    c_accent = _hex_to_rl_color(COLOR_ACCENT_BLUE)
    c_secondary = _hex_to_rl_color(COLOR_SECONDARY_TEXT)

    h1 = ParagraphStyle(
        "h1", parent=styles["Heading1"], fontSize=20, textColor=c_primary, spaceAfter=4
    )
    h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"], fontSize=14, textColor=c_accent, spaceAfter=4
    )
    body = ParagraphStyle(
        "body", parent=styles["Normal"], fontSize=10, textColor=c_primary, leading=14
    )
    caption = ParagraphStyle(
        "caption",
        parent=styles["Normal"],
        fontSize=8,
        textColor=c_secondary,
        leading=11,
    )
    bold_body = ParagraphStyle("bold_body", parent=body, fontName="Helvetica-Bold")

    story = []

    # ── Header ──────────────────────────────────────────────────────────────
    story.append(Paragraph("SookshmaJal — PMFBY Drought Loss Dossier", h1))
    story.append(
        Paragraph(
            f"Team VECTORZZ · Hackwarts 2026 · Generated: {generated_at}", caption
        )
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=_hex_to_rl_color(COLOR_SURFACE))
    )
    story.append(Spacer(1, 6 * mm))

    # ── Farmer & Plot Details ───────────────────────────────────────────────
    story.append(Paragraph("1. Farmer & Plot Details", h2))
    farm_data = [
        ["Field", "Value"],
        ["Farmer Name", farmer],
    ]
    if phone:
        farm_data.append(["Phone Number", str(phone)])
    farm_data.extend(
        [
            ["Crop Type", crop],
            ["Taluk / District", f"{taluk} / {district}, Karnataka"],
        ]
    )
    if village or hobli:
        loc_parts = [p for p in [village, hobli] if p]
        farm_data.append(["Village / Hobli", " / ".join(loc_parts)])
    if survey_no:
        farm_data.append(["RTC / Bhoomi Survey No.", str(survey_no)])
    if irrigation_source:
        farm_data.append(["Water Source", str(irrigation_source)])
    if observed_symptoms:
        farm_data.append(["Observed Symptoms", ", ".join(map(str, observed_symptoms))])
    if pmfby_eligible:
        farm_data.append(["PMFBY Eligibility", str(pmfby_eligible)])
    dist_txt = f"{float(distance_km):.2f} km" if distance_km is not None else "N/A"
    farm_data.append(
        [
            "Photo Geolock & Region",
            f"{geolock_status} (Region Match: {'Yes' if region_match else 'No'}, Distance: {dist_txt})",
        ]
    )
    farm_data.extend(
        [
            ["Plot Area", f"{area:.2f} acres"],
            ["Plot ID", plot_id],
            ["Centroid (Lat, Lon)", f"{lat:.6f}°N, {lon:.6f}°E"],
            ["Sentinel-2 Scene Date", scene_date],
            ["Cloud Cover", f"{cloud_cover:.1f}%"],
            ["Data Source", data_source],
        ]
    )
    farm_table = Table(farm_data, colWidths=[60 * mm, 110 * mm])
    farm_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), c_accent),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, _hex_to_rl_color(COLOR_SURFACE)],
                ),
                ("GRID", (0, 0), (-1, -1), 0.5, _hex_to_rl_color("#D2D2D7")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(farm_table)
    story.append(Spacer(1, 6 * mm))

    # ── Satellite Indices ───────────────────────────────────────────────────
    story.append(Paragraph("2. Satellite Moisture Indices (Sentinel-2 L2A)", h2))
    sat_data = [
        ["Index", "Value", "Interpretation"],
        ["NDVI (Vegetation Health)", f"{ndvi:.4f}", _ndvi_interp(ndvi)],
        ["NDMI (Moisture Stress)", f"{ndmi:.4f}", _ndmi_interp(ndmi)],
        ["NDRE (Red-Edge Chlorophyll)", f"{ndre:.4f}", _ndre_interp(ndre)],
    ]
    sat_table = Table(sat_data, colWidths=[65 * mm, 30 * mm, 75 * mm])
    sat_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _drought_color(drought_stage)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, _hex_to_rl_color(COLOR_SURFACE)],
                ),
                ("GRID", (0, 0), (-1, -1), 0.5, _hex_to_rl_color("#D2D2D7")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(sat_table)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"<b>Drought Assessment: {stage_label}</b>", bold_body))
    story.append(Paragraph(f"Recommendation: {rec_en}", body))

    ts = payload.get("time_series") or {}
    if ts.get("dates"):
        onset_date = (
            ts.get("stress_onset_date") or "None detected (within normal baseline)"
        )
        days_since = ts.get("days_since_stress_onset")
        onset_note = f"Mid-Season Stress Onset: <b>{onset_date}</b>" + (
            f" ({days_since} days prior to latest scene — post-harvest audit trail anchored)"
            if days_since
            else ""
        )
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(onset_note, body))

    story.append(Spacer(1, 6 * mm))

    # ── Hydro-Met Data ──────────────────────────────────────────────────────
    story.append(Paragraph("3. FAO-56 Hydro-Meteorological Assessment", h2))
    hm_data = [
        ["Parameter", "Value"],
        ["FAO-56 Reference ET₀", f"{et0:.2f} mm/day"],
        ["7-Day Precipitation", f"{precip:.1f} mm"],
        ["Water Deficit Rate", f"{deficit:.2f} mm/day"],
        ["Soil Moisture (0–7 cm)", f"{soil_m:.1f}%"],
        ["Survival Water Needed (7-day)", f"{v_surv:,.0f} litres"],
    ]
    hm_table = Table(hm_data, colWidths=[90 * mm, 80 * mm])
    hm_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), c_accent),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, _hex_to_rl_color(COLOR_SURFACE)],
                ),
                ("GRID", (0, 0), (-1, -1), 0.5, _hex_to_rl_color("#D2D2D7")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(hm_table)
    story.append(Spacer(1, 6 * mm))

    # ── Geotagged Field Evidence (if photo or GPS captured) ─────────────────
    has_photo_file = bool(photo_path and Path(str(photo_path)).exists())
    if photo_sha256 or has_photo_file or geolock_status != "MISSING_GPS":
        story.append(Paragraph("3b. Geotagged Field Evidence & Region Match", h2))
        dist_str = f"{float(distance_km):.2f} km" if distance_km is not None else "N/A"
        story.append(
            Paragraph(
                f"<b>Geolock Status:</b> {geolock_status} · "
                f"<b>Region Match:</b> {'YES' if region_match else 'NO'} · "
                f"<b>Distance to Plot:</b> {dist_str} · "
                f"<b>Photo Attached:</b> {'Yes' if has_photo_file else 'No (GPS simulation / no camera file)'}",
                body,
            )
        )
        if photo_lat is not None and photo_lon is not None:
            story.append(
                Paragraph(
                    f"<b>Captured GPS:</b> {float(photo_lat):.6f}°N, {float(photo_lon):.6f}°E"
                    + (f" · <b>Timestamp:</b> {photo_timestamp}" if photo_timestamp else ""),
                    body,
                )
            )
        if photo_sha256:
            story.append(
                Paragraph(
                    f"<b>Photo SHA-256:</b> <font name='Courier' size='8'>{photo_sha256}</font>",
                    body,
                )
            )
        if has_photo_file:
            try:
                from PIL import Image as PILImage

                with PILImage.open(str(photo_path)) as pil_im:
                    w_px, h_px = pil_im.size
                aspect = (h_px / w_px) if w_px > 0 else 0.75
                img_w = 55 * mm
                img_h = min(45 * mm, img_w * aspect)
                story.append(Spacer(1, 2 * mm))
                story.append(Image(str(photo_path), width=img_w, height=img_h))
            except Exception as exc:
                logger.warning("Could not embed field photo in PDF: %s", exc)
        story.append(Spacer(1, 5 * mm))

    # ── Preliminary SHA-256 (content hash without itself) ──────────────────
    hash_payload = {k: v for k, v in payload.items() if k != "photo_path"}
    content_for_hash = json.dumps(hash_payload, sort_keys=True, default=str).encode("utf-8")
    sha256 = _sha256_bytes(content_for_hash)

    story.append(Paragraph("4. Tamper-Evident SHA-256 Ground-Truth Hash", h2))
    story.append(
        Paragraph(
            "This dossier is cryptographically anchored to the analysis payload. "
            "The SHA-256 hash below uniquely identifies this claim and can be verified "
            "at the SookshmaJal verification endpoint.",
            body,
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"<font name='Courier' size='8'>{sha256}</font>", body))
    story.append(Spacer(1, 4 * mm))

    # ── QR Code ─────────────────────────────────────────────────────────────
    verify_url = f"{verify_base_url}/api/verify/{sha256}"
    qr_img = _make_qr_image(verify_url, size_mm=42.0)
    if qr_img:
        story.append(Paragraph("Scan to verify this dossier:", caption))
        story.append(qr_img)
        story.append(Paragraph(f"URL: {verify_url}", caption))
    story.append(Spacer(1, 6 * mm))

    # ── Disclaimer ───────────────────────────────────────────────────────────
    story.append(
        HRFlowable(width="100%", thickness=0.5, color=_hex_to_rl_color(COLOR_SURFACE))
    )
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            "DISCLAIMER: This dossier is generated by SookshmaJal, an AI-assisted satellite "
            "remote sensing tool, for the purpose of PMFBY crop insurance claim support. "
            "The indices and assessments herein are derived from Sentinel-2 L2A satellite data "
            "and Open-Meteo weather APIs. This document does not constitute a final insurance "
            "claim determination. Field verification by a licensed agronomist is recommended.",
            caption,
        )
    )

    # ── Build PDF bytes ──────────────────────────────────────────────────────
    doc.build(story)
    pdf_bytes = buf.getvalue()

    # ── Write to disk ────────────────────────────────────────────────────────
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_farmer = "".join(c for c in farmer if c.isalnum() or c == "_")[:30]
    filename = f"PMFBY_{safe_farmer}_{timestamp}_{sha256[:8]}.pdf"
    pdf_path = str(Path(output_dir) / filename)

    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    logger.info("PMFBY PDF generated: %s (SHA-256: %s)", pdf_path, sha256)
    return pdf_path, sha256


def _ndvi_interp(v: float) -> str:
    if v > 0.6:
        return "Dense vegetation – healthy"
    elif v > 0.4:
        return "Moderate vegetation"
    elif v > 0.2:
        return "Sparse / stressed vegetation"
    elif v > 0.0:
        return "Very sparse / bare soil"
    else:
        return "Bare soil / water"


def _ndmi_interp(v: float) -> str:
    if v > 0.2:
        return "High moisture – no stress"
    elif v > 0.0:
        return "Adequate moisture"
    elif v > -0.2:
        return "Low moisture – early stress"
    elif v > -0.4:
        return "Moisture deficit – moderate drought"
    else:
        return "Severe moisture deficit"


def _ndre_interp(v: float) -> str:
    if v > 0.4:
        return "High chlorophyll – healthy canopy"
    elif v > 0.2:
        return "Moderate chlorophyll"
    elif v > 0.0:
        return "Low chlorophyll – stress indicated"
    else:
        return "Chlorophyll depleted – senescence"
