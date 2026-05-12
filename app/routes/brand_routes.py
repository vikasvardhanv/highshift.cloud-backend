from __future__ import annotations

import io
import json
import os
import re
import zipfile
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
except ImportError:  # pragma: no cover - deployment should install pillow from requirements.
    Image = ImageEnhance = ImageFilter = ImageOps = None

from app.utils.auth import get_current_user, AuthUser
from app.db.postgres import fetch_user_by_id, update_user

router = APIRouter(prefix="/brand", tags=["BrandKit"])

BRAND_ASSET_FORMATS = {
    "social_square": {"width": 1080, "height": 1080, "description": "Social square"},
    "instagram_portrait": {"width": 1080, "height": 1350, "description": "Instagram portrait"},
    "instagram_story": {"width": 1080, "height": 1920, "description": "Instagram story"},
    "x_header": {"width": 1500, "height": 500, "description": "X header"},
    "linkedin_post": {"width": 1200, "height": 627, "description": "LinkedIn post"},
    "facebook_post": {"width": 1200, "height": 630, "description": "Facebook post"},
    "youtube_thumbnail": {"width": 1280, "height": 720, "description": "YouTube thumbnail"},
    "website_og": {"width": 1200, "height": 630, "description": "Website share image"},
    "hero_desktop": {"width": 1280, "height": 720, "description": "Desktop hero"},
    "hero_mobile": {"width": 800, "height": 600, "description": "Mobile hero"},
    "app_icon": {"width": 512, "height": 512, "description": "App icon"},
    "favicon": {"width": 48, "height": 48, "description": "Favicon"},
    "profile_picture": {"width": 400, "height": 400, "description": "Profile picture"},
    "cover_photo": {"width": 1920, "height": 1080, "description": "Cover photo"},
    "email_header": {"width": 600, "height": 200, "description": "Email header"},
    "presentation_slide": {"width": 1920, "height": 1080, "description": "Presentation slide"},
}

BRAND_ASSET_CATEGORIES = {
    "Social": ["social_square", "instagram_portrait", "instagram_story", "x_header", "linkedin_post", "facebook_post", "youtube_thumbnail"],
    "Web": ["website_og", "hero_desktop", "hero_mobile", "cover_photo"],
    "Identity": ["app_icon", "favicon", "profile_picture"],
    "Business": ["email_header", "presentation_slide"],
}

BRAND_ASSET_PRESETS = {
    "social_pack": ["social_square", "instagram_portrait", "instagram_story", "x_header", "linkedin_post", "facebook_post"],
    "website_pack": ["website_og", "hero_desktop", "hero_mobile", "cover_photo", "favicon"],
    "identity_pack": ["app_icon", "favicon", "profile_picture", "email_header"],
    "complete_pack": list(BRAND_ASSET_FORMATS.keys()),
}

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
ALLOWED_OUTPUT_FORMATS = {"png", "jpg", "webp", "ico"}
MAX_BRAND_ASSET_UPLOAD_MB = int(os.getenv("BRAND_ASSET_MAX_UPLOAD_MB", "16"))


def _brand_defaults() -> dict[str, Any]:
    return {
        "company_name": "",
        "industry": "",
        "website": "",
        "tone": "Professional",
        "description": "",
        "keywords": [],
        "colors": [],
        "asset_preferences": {},
    }


def _clean_filename(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9._-]+", "-", value or "highshift-brand")
    return name.strip("-._") or "highshift-brand"


def _parse_csv(value: str | None, allowed: set[str] | None = None) -> list[str]:
    items = [item.strip() for item in (value or "").split(",") if item.strip()]
    if allowed is not None:
        items = [item for item in items if item in allowed]
    return list(dict.fromkeys(items))


def _hex_to_rgb(value: str, fallback=(255, 255, 255)) -> tuple[int, int, int]:
    clean = (value or "").strip().lstrip("#")
    if len(clean) == 3:
        clean = "".join(char * 2 for char in clean)
    if len(clean) != 6:
        return fallback
    try:
        return tuple(int(clean[index:index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return fallback


def _dominant_color(image: Image.Image) -> tuple[int, int, int]:
    sample = image.convert("RGBA").resize((64, 64))
    colors = sample.getcolors(64 * 64) or []
    colors = [
        (count, color[:3])
        for count, color in colors
        if color[3] > 16 and not all(channel > 245 for channel in color[:3])
    ]
    if not colors:
        return (31, 41, 55)
    return max(colors, key=lambda item: item[0])[1]


def _preprocess_image(image: Image.Image, options: dict[str, Any]) -> Image.Image:
    image = image.convert("RGBA")
    if options.get("auto_crop"):
        bbox = image.getbbox()
        if bbox:
            pad = int(options.get("crop_padding", 10))
            left, top, right, bottom = bbox
            image = image.crop((
                max(0, left - pad),
                max(0, top - pad),
                min(image.width, right + pad),
                min(image.height, bottom + pad),
            ))
    if options.get("grayscale"):
        image = ImageOps.grayscale(image).convert("RGBA")
    if options.get("bw"):
        image = ImageOps.grayscale(image).point(lambda pixel: 0 if pixel < 128 else 255).convert("RGBA")
    if options.get("invert"):
        r, g, b, a = image.split()
        inverted = ImageOps.invert(Image.merge("RGB", (r, g, b)))
        image = Image.merge("RGBA", (*inverted.split(), a))
    if options.get("enhance_contrast"):
        image = ImageEnhance.Contrast(image).enhance(1.45)
    if options.get("saturation", 1.0) != 1.0:
        image = ImageEnhance.Color(image).enhance(float(options.get("saturation", 1.0)))
    if options.get("brightness", 1.0) != 1.0:
        image = ImageEnhance.Brightness(image).enhance(float(options.get("brightness", 1.0)))
    if options.get("sharpen"):
        image = image.filter(ImageFilter.UnsharpMask(radius=float(options.get("sharpen_radius", 1.0))))
    if options.get("apply_blur"):
        image = image.filter(ImageFilter.GaussianBlur(radius=float(options.get("blur_radius", 2.0))))
    return image


def _compose_asset(image: Image.Image, width: int, height: int, fill_mode: str, background_color: str) -> Image.Image:
    image = image.copy().convert("RGBA")
    if fill_mode == "cover":
        ratio = max(width / image.width, height / image.height)
        resized = image.resize((max(1, round(image.width * ratio)), max(1, round(image.height * ratio))), Image.LANCZOS)
        left = (resized.width - width) // 2
        top = (resized.height - height) // 2
        return resized.crop((left, top, left + width, top + height)).convert("RGBA")

    image.thumbnail((width, height), Image.LANCZOS)
    if fill_mode == "transparent":
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    else:
        bg = _hex_to_rgb(background_color, _dominant_color(image))
        canvas = Image.new("RGBA", (width, height), bg + (255,))
    x = (width - image.width) // 2
    y = (height - image.height) // 2
    canvas.paste(image, (x, y), image)
    return canvas


def _save_asset(image: Image.Image, output_format: str) -> tuple[bytes, str]:
    buffer = io.BytesIO()
    fmt = output_format.lower()
    if fmt == "jpg":
        bg = Image.new("RGB", image.size, (255, 255, 255))
        bg.paste(image, mask=image.getchannel("A") if image.mode == "RGBA" else None)
        bg.save(buffer, format="JPEG", quality=94, optimize=True)
        media_type = "image/jpeg"
    elif fmt == "webp":
        image.save(buffer, format="WEBP", quality=92, method=6)
        media_type = "image/webp"
    elif fmt == "ico":
        sizes = [(16, 16), (32, 32), (48, 48)]
        image.save(buffer, format="ICO", sizes=sizes)
        media_type = "image/x-icon"
    else:
        image.save(buffer, format="PNG", optimize=True, compress_level=9)
        media_type = "image/png"
    return buffer.getvalue(), media_type


def _bool_form(value: str | None) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "on"}


@router.get("")
async def get_brand_settings(
    user: AuthUser = Depends(get_current_user)
):
    user_row = await fetch_user_by_id(user.id)
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    
    brand = {**_brand_defaults(), **(user_row.get("brand_kit") or {})}
    return {"brand": brand}

@router.post("")
async def update_brand_settings(
    payload: dict,
    user: AuthUser = Depends(get_current_user)
):
    existing = {}
    user_row = await fetch_user_by_id(user.id)
    if user_row and isinstance(user_row.get("brand_kit"), dict):
        existing = user_row["brand_kit"]

    brand_kit = {
        **existing,
        "company_name": payload.get("company_name", ""),
        "industry": payload.get("industry", ""),
        "website": payload.get("website", ""),
        "tone": payload.get("tone", "Professional"),
        "description": payload.get("description", ""),
        "keywords": payload.get("keywords", []),
        "colors": payload.get("colors", existing.get("colors", [])),
        "asset_preferences": payload.get("asset_preferences", existing.get("asset_preferences", {})),
    }
    await update_user(user.id, {"brand_kit": brand_kit})
    return {"brand": brand_kit, "message": "Brand settings saved"}


@router.get("/assets/formats")
async def get_brand_asset_formats(user: AuthUser = Depends(get_current_user)):
    return {
        "formats": BRAND_ASSET_FORMATS,
        "categories": BRAND_ASSET_CATEGORIES,
        "presets": BRAND_ASSET_PRESETS,
        "output_formats": sorted(ALLOWED_OUTPUT_FORMATS),
        "max_upload_mb": MAX_BRAND_ASSET_UPLOAD_MB,
    }


@router.post("/assets/generate")
async def generate_brand_assets(
    file: UploadFile = File(...),
    selected_formats: str = Form(""),
    output_formats: str = Form("png"),
    fill_mode: str = Form("contain"),
    background_color: str = Form("#111827"),
    grayscale: str = Form("false"),
    bw: str = Form("false"),
    invert: str = Form("false"),
    enhance_contrast: str = Form("false"),
    apply_blur: str = Form("false"),
    blur_radius: str = Form("2"),
    saturation: str = Form("1"),
    brightness: str = Form("1"),
    sharpen: str = Form("false"),
    sharpen_radius: str = Form("1"),
    auto_crop: str = Form("false"),
    crop_padding: str = Form("10"),
    user: AuthUser = Depends(get_current_user),
):
    if Image is None:
        raise HTTPException(status_code=503, detail="Brand asset generation requires Pillow. Install backend requirements and restart.")

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Upload a PNG, JPG, WEBP, or GIF image.")

    raw = await file.read()
    if len(raw) > MAX_BRAND_ASSET_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Image must be {MAX_BRAND_ASSET_UPLOAD_MB}MB or smaller.")

    selected = _parse_csv(selected_formats)
    selected = [item for item in selected if item in BRAND_ASSET_FORMATS]
    if not selected:
        selected = BRAND_ASSET_PRESETS["social_pack"]

    outputs = _parse_csv(output_formats, ALLOWED_OUTPUT_FORMATS) or ["png"]
    if "ico" in outputs and "favicon" not in selected:
        outputs = [item for item in outputs if item != "ico"] or ["png"]

    if fill_mode not in {"contain", "cover", "transparent"}:
        fill_mode = "contain"

    try:
        source = Image.open(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read the uploaded image.") from exc

    options = {
        "grayscale": _bool_form(grayscale),
        "bw": _bool_form(bw),
        "invert": _bool_form(invert),
        "enhance_contrast": _bool_form(enhance_contrast),
        "apply_blur": _bool_form(apply_blur),
        "blur_radius": float(blur_radius or 2),
        "saturation": float(saturation or 1),
        "brightness": float(brightness or 1),
        "sharpen": _bool_form(sharpen),
        "sharpen_radius": float(sharpen_radius or 1),
        "auto_crop": _bool_form(auto_crop),
        "crop_padding": int(crop_padding or 10),
    }

    processed = _preprocess_image(source, options)
    brand_name = _clean_filename((await fetch_user_by_id(user.id) or {}).get("brand_kit", {}).get("company_name") or "highshift-brand")
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")

    zip_buffer = io.BytesIO()
    manifest = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "brand": brand_name,
        "formats": [],
    }

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for format_name in selected:
            format_config = BRAND_ASSET_FORMATS[format_name]
            asset = _compose_asset(
                processed,
                format_config["width"],
                format_config["height"],
                fill_mode,
                background_color,
            )
            for output_format in outputs:
                if output_format == "ico" and format_name != "favicon":
                    continue
                asset_bytes, _ = _save_asset(asset, output_format)
                extension = "jpg" if output_format == "jpg" else output_format
                filename = f"{brand_name}_{format_name}.{extension}"
                zip_file.writestr(filename, asset_bytes)
                manifest["formats"].append({
                    "filename": filename,
                    "format": format_name,
                    "output": output_format,
                    "width": format_config["width"],
                    "height": format_config["height"],
                    "description": format_config["description"],
                })
        zip_file.writestr("manifest.json", json.dumps(manifest, indent=2))

    zip_buffer.seek(0)
    download_name = f"{brand_name}_highshift_assets_{timestamp}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )
