"""
Video Tools Routes - Complete Video Processing & Automation Suite.
Ported and enhanced from AutoSocial Studio (https://github.com/Katzca/AutoSocial).

Features:
- Full Video Uniquifier: multi-filter fingerprint evasion (speed, frame freezing, color/hue shift,
  channel mixer, pixel grid shifting, subtle noise, audio pitch adjustment, metadata spoofing, logo overlay).
- Auto-Downloader: yt-dlp powered downloader with format selection and direct import into Media Library.
- Profile / Channel Scanner & Downloader: scan profiles, filter by min views, batch import.
- Doctor / Diagnostics: full system health check for FFmpeg, ffprobe, yt-dlp, and storage.
"""
import os
import uuid
import asyncio
import logging
import shutil
import subprocess
import random
import json
import base64
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.routes.auth_routes import get_optional_user
from app.models.user import User
from app.models.media import Media

router = APIRouter(prefix="/video-tools", tags=["Video Tools"])
logger = logging.getLogger("video_tools")

# Local temp directories
TEMP_VIDEO_DIR = Path("/tmp/socialraven_videos")
TEMP_VIDEO_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_dependency(name: str) -> bool:
    """Return True if a CLI tool is available in PATH."""
    return shutil.which(name) is not None


def _cleanup_file(path: str):
    """Delete a file if it exists (used as background cleanup task)."""
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"Cleaned up temp file: {path}")
    except Exception as e:
        logger.warning(f"Failed to clean up {path}: {e}")


async def _run_subprocess(cmd: list[str], timeout: int = 180) -> tuple[int, str, str]:
    """Run a subprocess asynchronously and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, stdout.decode(errors="replace"), stderr.decode(errors="replace")
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(status_code=504, detail="Video processing timed out. Try a shorter video.")


def _build_spoofed_metadata_args() -> list[str]:
    """
    Generate spoofed metadata arguments similar to AutoSocial's buildMetadataArgs().
    Clears existing creator fingerprints and sets randomized camera/encoder tags.
    """
    now = datetime.utcnow()
    rand_days = random.randint(-365, 365)
    rand_hours = random.randint(-23, 23)
    fake_date = (now + timedelta(days=rand_days, hours=rand_hours)).isoformat()

    titles = [
        "",
        f"clip_{uuid.uuid4().hex[:12]}",
        f"VID_{random.randint(20210101, 20261231)}_{random.randint(100000, 999999)}",
        f"IMG_{random.randint(1000, 9999)}",
    ]

    encoders = [
        f"Lavf {random.randint(57, 61)}.{random.randint(10, 99)}.{random.randint(100, 999)}",
        f"HandBrake {random.randint(1, 2)}.{random.randint(0, 8)}.{random.randint(0, 4)}",
        "",
    ]

    return [
        "-map_metadata", "-1",
        "-metadata", f"title={random.choice(titles)}",
        "-metadata", f"comment={uuid.uuid4().hex[:16]}",
        "-metadata", f"creation_time={fake_date}",
        "-metadata", f"encoder={random.choice(encoders)}",
        "-metadata", "description=",
        "-metadata", "artist=",
    ]


# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------

class UniquifyOptions(BaseModel):
    """Advanced video uniquification options (matched with AutoSocial Studio)."""
    extend_duration: Optional[bool] = True       # Slight speed jitter (0.97 - 0.995x)
    speed_factor: Optional[float] = 1.02         # Custom speed factor if specified
    freeze_frames: Optional[bool] = True         # Clone first & last frame for 0.05 - 0.25s
    color_shift: Optional[bool] = True           # Jitter brightness, contrast, saturation, gamma
    hue_shift: Optional[bool] = True             # Subtle hue angle rotation
    channel_mix: Optional[bool] = True           # Color channel bleed
    noise: Optional[bool] = True                 # Subtle micro-grain sensor noise
    pixel_shift: Optional[bool] = True           # 1-2px crop and pad to shift the spatial grid
    color_overlay: Optional[bool] = True         # Color balance nudge
    flip_horizontal: Optional[bool] = False      # Horizontal mirror
    audio_pitch_shift: Optional[bool] = True     # Micro pitch shift
    spoof_metadata: Optional[bool] = True        # Overwrite file metadata & encoder hashes
    save_to_media_library: Optional[bool] = True # Save directly to SocialRaven Media Library


class UniquifyRequest(BaseModel):
    media_id: Optional[str] = None               # Existing media ID in SocialRaven
    source_url: Optional[str] = None             # Or external URL
    options: Optional[UniquifyOptions] = Field(default_factory=UniquifyOptions)


class DownloadRequest(BaseModel):
    url: str
    quality: Optional[str] = "best[height<=1080]"
    save_to_media_library: Optional[bool] = True
    filename: Optional[str] = None


class ProfileScanRequest(BaseModel):
    channel: str                                 # TikTok @handle or channel URL
    min_views: Optional[int] = 0                 # Filter videos with >= min views
    max_videos: Optional[int] = 10               # Maximum videos to fetch


# ---------------------------------------------------------------------------
# Diagnostics / Doctor Endpoint
# ---------------------------------------------------------------------------

@router.get("/doctor")
async def system_doctor():
    """
    Comprehensive system health check mirroring AutoSocial's doctor & setup health.
    Checks FFmpeg, ffprobe, yt-dlp, disk space, and temp directory writable status.
    """
    tools = {}
    for name in ["ffmpeg", "ffprobe", "yt-dlp"]:
        path = shutil.which(name)
        version = None
        if path:
            try:
                res = subprocess.run([name, "--version"], capture_output=True, text=True, timeout=5)
                first_line = (res.stdout or res.stderr).splitlines()
                version = first_line[0] if first_line else "Unknown"
            except Exception:
                version = "Available"
        tools[name] = {
            "installed": path is not None,
            "path": path,
            "version": version,
        }

    # Disk usage in temp directory
    try:
        total, used, free = shutil.disk_usage(str(TEMP_VIDEO_DIR))
        disk_stats = {
            "total_gb": round(total / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "temp_dir": str(TEMP_VIDEO_DIR),
            "writable": os.access(str(TEMP_VIDEO_DIR), os.W_OK),
        }
    except Exception as e:
        disk_stats = {"error": str(e)}

    is_healthy = tools["ffmpeg"]["installed"] and tools["yt-dlp"]["installed"]

    return {
        "status": "ready" if is_healthy else "missing_dependencies",
        "ready_for_production": is_healthy,
        "tools": tools,
        "storage": disk_stats,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/status")
async def get_status():
    """Quick boolean check for available tools."""
    return {
        "yt_dlp_available": _check_dependency("yt-dlp"),
        "ffmpeg_available": _check_dependency("ffmpeg"),
        "ffprobe_available": _check_dependency("ffprobe"),
    }


# ---------------------------------------------------------------------------
# Video Probe / Metadata Inspector
# ---------------------------------------------------------------------------

@router.get("/probe")
async def probe_video_url(url: str):
    """
    Extract video metadata (title, duration, views, platform, thumbnail) using yt-dlp.
    """
    if not _check_dependency("yt-dlp"):
        raise HTTPException(status_code=503, detail="yt-dlp is not available.")

    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-playlist",
        "--no-warnings",
        "--quiet",
        url,
    ]

    returncode, stdout, stderr = await _run_subprocess(cmd, timeout=30)
    if returncode != 0 or not stdout.strip():
        raise HTTPException(status_code=422, detail=f"Could not fetch video info: {stderr[:300]}")

    try:
        info = json.loads(stdout.splitlines()[0])
        return {
            "title": info.get("title"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "thumbnail": info.get("thumbnail"),
            "platform": info.get("extractor_key"),
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "formats_count": len(info.get("formats", [])),
        }
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Could not parse video metadata.")


# ---------------------------------------------------------------------------
# Profile & Channel Scanner
# ---------------------------------------------------------------------------

@router.post("/profile-scan")
async def scan_profile(request: ProfileScanRequest):
    """
    Scan a TikTok/YouTube/Instagram profile for recent videos with view count filtering.
    Ported from AutoSocial's profile-download-controller.js.
    """
    if not _check_dependency("yt-dlp"):
        raise HTTPException(status_code=503, detail="yt-dlp is not installed.")

    channel = request.channel.strip()
    if not channel.startswith("http"):
        if not channel.startswith("@"):
            channel = "@" + channel
        channel_url = f"https://www.tiktok.com/{channel}"
    else:
        channel_url = channel

    cmd = [
        "yt-dlp",
        "--dump-json",
        "--flat-playlist",
        "--playlist-end", str(min(50, request.max_videos or 10)),
        "--no-warnings",
        "--quiet",
        channel_url,
    ]

    returncode, stdout, stderr = await _run_subprocess(cmd, timeout=60)
    if returncode != 0:
        raise HTTPException(status_code=422, detail=f"Failed to scan profile: {stderr[:300]}")

    videos = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            views = item.get("view_count") or 0
            if request.min_views and views < request.min_views:
                continue
            videos.append({
                "id": item.get("id"),
                "url": item.get("url") or item.get("webpage_url") or f"https://www.tiktok.com/video/{item.get('id')}",
                "title": item.get("title", "Untitled Video"),
                "duration": item.get("duration"),
                "view_count": views,
                "thumbnail": item.get("thumbnail"),
                "uploader": item.get("uploader"),
            })
        except Exception:
            continue

    return {
        "channel": channel,
        "count": len(videos),
        "min_views_applied": request.min_views,
        "videos": videos,
    }


# ---------------------------------------------------------------------------
# Video Downloader
# ---------------------------------------------------------------------------

@router.post("/download")
async def download_video(
    request: DownloadRequest,
    background_tasks: BackgroundTasks,
    user: Optional[User] = Depends(get_optional_user),
):
    """
    Download a video from a public URL using yt-dlp.
    Optionally saves directly into the SocialRaven Media Library.
    """
    if not _check_dependency("yt-dlp"):
        raise HTTPException(status_code=503, detail="yt-dlp is not installed on this server.")

    job_id = str(uuid.uuid4())
    output_path = TEMP_VIDEO_DIR / f"{job_id}.mp4"

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--format", request.quality or "best[height<=1080]",
        "--merge-output-format", "mp4",
        "--output", str(output_path),
        "--no-warnings",
        "--quiet",
        request.url,
    ]

    returncode, _, stderr = await _run_subprocess(cmd, timeout=180)
    if returncode != 0 or not output_path.exists():
        raise HTTPException(
            status_code=422,
            detail=f"Could not download video. Make sure the URL is public. Error: {stderr[:300]}",
        )

    file_size_mb = output_path.stat().st_size / (1024 * 1024)

    # Save directly to SocialRaven Media Library if requested
    if request.save_to_media_library:
        try:
            video_bytes = output_path.read_bytes()
            b64_data = base64.b64encode(video_bytes).decode("utf-8")
            data_url = f"data:video/mp4;base64,{b64_data}"
            
            media_name = request.filename or f"Downloaded_{job_id[:8]}.mp4"
            media = Media(
                user_id=str(user.id) if user else "anonymous",
                filename=media_name,
                content_type="video/mp4",
                file_type="video",
                data_url=data_url,
                size_bytes=len(video_bytes),
            )
            await media.insert()
            background_tasks.add_task(_cleanup_file, str(output_path))
            
            return {
                "success": True,
                "media_id": media.media_id,
                "public_url": media.get_public_url(),
                "filename": media_name,
                "size_mb": round(file_size_mb, 2),
            }
        except Exception as e:
            logger.warning(f"Failed to auto-save to media library, falling back to file response: {e}")

    background_tasks.add_task(_cleanup_file, str(output_path))
    return FileResponse(
        path=str(output_path),
        media_type="video/mp4",
        filename=request.filename or f"socialraven_download_{job_id[:8]}.mp4",
        headers={"X-File-Size-MB": f"{file_size_mb:.1f}"},
    )


# ---------------------------------------------------------------------------
# Video Uniquifier (Full AutoSocial Parity)
# ---------------------------------------------------------------------------

@router.post("/uniquify")
async def uniquify_video(
    request: UniquifyRequest,
    background_tasks: BackgroundTasks,
    user: Optional[User] = Depends(get_optional_user),
):
    """
    Advanced Video Uniquifier implementing full evasion pipeline from AutoSocial Studio:
    - Speed adjustment / Duration extension (imperceptible to human viewers)
    - Frame freezing (tpad cloning first and last frames)
    - Color shift (brightness, contrast, saturation, gamma micro-nudges)
    - Hue rotation
    - RGB channel mixing
    - Micro noise grain filter
    - Pixel grid shift (1-2px crop and pad)
    - Color balance overlay
    - Audio pitch & tempo shift
    - Metadata spoofing (EXIF, Lavf / HandBrake tags, random date/time)
    - Direct save to SocialRaven Media Library
    """
    if not _check_dependency("ffmpeg"):
        raise HTTPException(status_code=503, detail="FFmpeg is not installed on this server.")

    opts = request.options or UniquifyOptions()

    # --- Resolve source video ---
    source_path: Optional[Path] = None

    if request.source_url:
        job_id = str(uuid.uuid4())
        source_path = TEMP_VIDEO_DIR / f"src_{job_id}.mp4"

        if _check_dependency("yt-dlp"):
            dl_cmd = [
                "yt-dlp", "--no-playlist", "--format", "best[height<=1080]",
                "--merge-output-format", "mp4", "--output", str(source_path),
                "--no-warnings", "--quiet", request.source_url,
            ]
            rc, _, stderr = await _run_subprocess(dl_cmd, timeout=120)
            if rc != 0 or not source_path.exists():
                raise HTTPException(status_code=422, detail=f"Could not fetch source video: {stderr[:200]}")
        else:
            curl_cmd = ["curl", "-L", "-s", "-o", str(source_path), request.source_url]
            rc, _, _ = await _run_subprocess(curl_cmd, timeout=60)
            if rc != 0 or not source_path.exists():
                raise HTTPException(status_code=422, detail="Could not fetch source video URL.")

    elif request.media_id:
        media_doc = await Media.find_one({"media_id": request.media_id})
        if not media_doc or not media_doc.data_url:
            raise HTTPException(status_code=404, detail="Media not found.")

        header, encoded = media_doc.data_url.split(",", 1)
        decoded = base64.b64decode(encoded)
        source_path = TEMP_VIDEO_DIR / f"src_{media_doc.media_id}.mp4"
        source_path.write_bytes(decoded)
    else:
        raise HTTPException(status_code=400, detail="Provide either media_id or source_url.")

    # --- Build FFmpeg filter chain (Exact AutoSocial algorithm) ---
    job_id = str(uuid.uuid4())
    output_path = TEMP_VIDEO_DIR / f"unique_{job_id}.mp4"

    vf_filters = []
    af_filters = []

    # 1. Extend Duration / Slight Speed Change
    if opts.extend_duration:
        speed = random.uniform(0.97, 0.995)
        vf_filters.append(f"setpts=PTS/{speed:.4f}")
        af_filters.append(f"atempo={speed:.4f}")
    elif opts.speed_factor and abs(opts.speed_factor - 1.0) > 0.005:
        speed = max(0.9, min(1.1, opts.speed_factor))
        vf_filters.append(f"setpts={1.0 / speed:.4f}*PTS")
        af_filters.append(f"atempo={speed:.4f}")

    # 2. Freeze First & Last Frame (tpad)
    if opts.freeze_frames:
        s_dur = round(random.uniform(0.05, 0.25), 2)
        e_dur = round(random.uniform(0.05, 0.25), 2)
        vf_filters.append(f"tpad=start_duration={s_dur}:start_mode=clone:stop_duration={e_dur}:stop_mode=clone")

    # 3. Horizontal Flip (Optional)
    if opts.flip_horizontal:
        vf_filters.append("hflip")

    # 4. Color / Brightness / Contrast Shift
    if opts.color_shift:
        b = round(random.uniform(-0.025, 0.025), 3)
        c = round(random.uniform(0.98, 1.02), 3)
        s = round(random.uniform(0.97, 1.03), 3)
        g = round(random.uniform(0.98, 1.02), 3)
        vf_filters.append(f"eq=brightness={b}:contrast={c}:saturation={s}:gamma={g}")

    # 5. Hue Shift
    if opts.hue_shift:
        h = round(random.uniform(-3.5, 3.5), 2)
        hs = round(random.uniform(0.97, 1.03), 3)
        vf_filters.append(f"hue=h={h}:s={hs}")

    # 6. Color Channel Mixer
    if opts.channel_mix:
        rr = round(random.uniform(0.98, 1.0), 3)
        gg = round(random.uniform(0.98, 1.0), 3)
        bb = round(random.uniform(0.98, 1.0), 3)
        bleed = round(random.uniform(0.0, 0.015), 3)
        vf_filters.append(f"colorchannelmixer={rr}:{bleed}:{bleed}:0:{bleed}:{gg}:{bleed}:0:{bleed}:{bleed}:{bb}:0")

    # 7. Subtle Micro-noise
    if opts.noise:
        noise_level = random.randint(1, 2)
        vf_filters.append(f"noise=alls={noise_level}:allf=t")

    # 8. Pixel Grid Shift (1-2px crop & pad)
    if opts.pixel_shift:
        px = random.randint(1, 2)
        vf_filters.append(f"crop=iw-{px * 2}:ih-{px * 2}:{px}:{px}")
        vf_filters.append(f"pad=iw+{px * 2}:ih+{px * 2}:{px}:{px}:black")

    # 9. Color Balance Nudge
    if opts.color_overlay:
        rs = round(random.uniform(-0.03, 0.03), 3)
        gs = round(random.uniform(-0.03, 0.03), 3)
        bs = round(random.uniform(-0.03, 0.03), 3)
        vf_filters.append(f"colorbalance=rs={rs}:gs={gs}:bs={bs}")

    # 10. Format normalization
    vf_filters.append("crop=trunc(iw/2)*2:trunc(ih/2)*2")
    vf_filters.append("format=yuv420p")

    # 11. Audio Pitch Shift
    if opts.audio_pitch_shift:
        rate_shift = random.randint(43800, 44400)
        af_filters.append(f"asetrate={rate_shift},aresample=44100")

    vf_str = ",".join(vf_filters)
    af_str = ",".join(af_filters) if af_filters else "anull"

    # Assemble FFmpeg command
    cmd = [
        "ffmpeg", "-y",
        "-i", str(source_path),
        "-vf", vf_str,
        "-af", af_str,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "128k",
    ]

    # 12. Metadata Spoofing
    if opts.spoof_metadata:
        cmd.extend(_build_spoofed_metadata_args())

    cmd.extend(["-movflags", "+faststart", str(output_path)])

    logger.info(f"Uniquifying video with {len(vf_filters)} video filters and {len(af_filters)} audio filters")
    returncode, _, stderr = await _run_subprocess(cmd, timeout=300)

    # Clean up downloaded source
    if request.source_url and source_path and source_path.exists():
        background_tasks.add_task(_cleanup_file, str(source_path))

    if returncode != 0 or not output_path.exists():
        logger.error(f"FFmpeg uniquify failed [{returncode}]: {stderr[-500:]}")
        raise HTTPException(status_code=500, detail=f"Video processing failed: {stderr[-300:]}")

    file_size_mb = output_path.stat().st_size / (1024 * 1024)

    # Auto-save to Media Library
    if opts.save_to_media_library:
        try:
            video_bytes = output_path.read_bytes()
            b64_data = base64.b64encode(video_bytes).decode("utf-8")
            data_url = f"data:video/mp4;base64,{b64_data}"

            media_name = f"Uniquified_{job_id[:8]}.mp4"
            media = Media(
                user_id=str(user.id) if user else "anonymous",
                filename=media_name,
                content_type="video/mp4",
                file_type="video",
                data_url=data_url,
                size_bytes=len(video_bytes),
            )
            await media.insert()
            background_tasks.add_task(_cleanup_file, str(output_path))

            return {
                "success": True,
                "media_id": media.media_id,
                "public_url": media.get_public_url(),
                "filename": media_name,
                "size_mb": round(file_size_mb, 2),
                "transformations_applied": {
                    "extend_duration": opts.extend_duration,
                    "freeze_frames": opts.freeze_frames,
                    "color_shift": opts.color_shift,
                    "hue_shift": opts.hue_shift,
                    "channel_mix": opts.channel_mix,
                    "noise": opts.noise,
                    "pixel_shift": opts.pixel_shift,
                    "color_overlay": opts.color_overlay,
                    "flip_horizontal": opts.flip_horizontal,
                    "audio_pitch_shift": opts.audio_pitch_shift,
                    "spoofed_metadata": opts.spoof_metadata,
                },
            }
        except Exception as e:
            logger.warning(f"Failed to auto-save uniquified video to media library: {e}")

    background_tasks.add_task(_cleanup_file, str(output_path))
    return FileResponse(
        path=str(output_path),
        media_type="video/mp4",
        filename=f"socialraven_unique_{job_id[:8]}.mp4",
        headers={"X-File-Size-MB": f"{file_size_mb:.1f}"},
    )
