#!/usr/bin/env python3
"""Assemble Malema v2 portrait debate video."""

import subprocess
import os
import sys

BASE = "/workspace/projects/malema-video-v2"
CLIPS = f"{BASE}/clips"
AUDIO = f"{BASE}/audio"
IMG = f"{BASE}/img"
OUT = f"{BASE}/segments"
FINAL = f"{BASE}/output"

os.makedirs(OUT, exist_ok=True)
os.makedirs(FINAL, exist_ok=True)

W, H = 1080, 1920

def run(cmd, desc=""):
    """Run ffmpeg command."""
    print(f"\n{'='*60}")
    print(f"  {desc}")
    print(f"{'='*60}")
    print(f"  cmd: {' '.join(cmd[:8])}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr[-500:]}")
        sys.exit(1)
    print(f"  OK")
    return result

def portrait_speaker(input_clip, output, duration=None):
    """Convert landscape clip to portrait with blurred background."""
    dur = f"-t {duration}" if duration else ""
    # Split video, blur one copy for bg, scale original to fit, overlay
    cmd = [
        "ffmpeg", "-y", "-i", input_clip,
        "-filter_complex",
        (
            f"[0:v]split=2[orig][bg];"
            f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},gblur=sigma=25[blurred];"
            f"[orig]scale={W}:-2,format=yuva420p[fg];"
            f"[blurred][fg]overlay=(W-w)/2:(H-h)/2,"
            f"format=yuv420p[v]"
        ),
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-r", "30",
        "-movflags", "+faststart",
    ]
    if duration:
        cmd += ["-t", str(duration)]
    cmd.append(output)
    return cmd

def freeze_intro(image, name, title, output, duration=3):
    """Create freeze frame intro with B&W, name overlay, slow zoom."""
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", image,
        "-filter_complex",
        (
            f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},"
            f"format=gray,eq=contrast=1.5:brightness=0.05,"
            f"zoompan=z='min(zoom+0.001,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={duration*30}:s={W}x{H}:fps=30,"
            f"drawtext=text='{name}':fontsize=64:fontcolor=white:"
            f"x=(w-text_w)/2:y=h*0.55:shadowcolor=black:shadowx=2:shadowy=2,"
            f"drawtext=text='{title}':fontsize=36:fontcolor=white@0.8:"
            f"x=(w-text_w)/2:y=h*0.62:shadowcolor=black:shadowx=1:shadowy=1,"
            f"format=yuv420p[v]"
        ),
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-r", "30", "-t", str(duration),
        "-movflags", "+faststart",
        output
    ]
    return cmd

def narrator_segment(audio_file, bg_image, output):
    """Create narrator segment with TTS audio over Ken Burns on background."""
    dur_cmd = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", audio_file],
        capture_output=True, text=True
    )
    dur = float(dur_cmd.stdout.strip())
    frames = int(dur * 30)
    
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", bg_image, "-i", audio_file,
        "-filter_complex",
        (
            f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},"
            f"eq=brightness=-0.1:saturation=0.6,"
            f"zoompan=z='min(zoom+0.0003,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s={W}x{H}:fps=30,"
            f"format=yuv420p[v]"
        ),
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-r", "30", "-t", str(dur),
        "-movflags", "+faststart",
        output
    ]
    return cmd

def title_segment(image, output, duration=4):
    """Create title card with zoom and fade."""
    frames = duration * 30
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", image,
        "-filter_complex",
        (
            f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},"
            f"zoompan=z='min(zoom+0.001,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s={W}x{H}:fps=30,"
            f"fade=t=in:st=0:d=1.5,fade=t=out:st={duration-1}:d=1,"
            f"format=yuv420p[v]"
        ),
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-r", "30", "-t", str(duration),
        "-an", "-movflags", "+faststart",
        output
    ]
    return cmd

def sources_segment(output, duration=6):
    """Create sources screen."""
    sources_lines = [
        "Sources:",
        "Pakenham, The Scramble for Africa",
        "Rodney, How Europe Underdeveloped Africa",
        "Marais, South Africa Pushed to the Limit",
        "Hochschild, King Leopold\\'s Ghost",
        "Fanon, The Wretched of the Earth",
        "Ross, The New Resource Curse"
    ]
    sources_text = "%{eif\\:n\\:d}"  # placeholder
    # Build each line as separate drawtext
    drawtexts = []
    y_start = H // 2 - len(sources_lines) * 30
    for i, line in enumerate(sources_lines):
        y = y_start + i * 50
        escaped = line.replace("'", "\\'").replace(":", "\\:")
        fs = 40 if i == 0 else 32
        fc = "white" if i == 0 else "white@0.85"
        drawtexts.append(
            f"drawtext=text='{escaped}':fontsize={fs}:fontcolor={fc}:"
            f"x=(w-text_w)/2:y={y}:shadowcolor=black:shadowx=1:shadowy=1"
        )
    filter_chain = ",".join(drawtexts)
    
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:d={duration}:r=30",
        "-filter_complex",
        (
            f"[0:v]{filter_chain},"
            f"fade=t=in:st=0:d=1,fade=t=out:st={duration-1.5}:d=1.5,"
            f"format=yuv420p[v]"
        ),
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-r", "30", "-t", str(duration),
        "-an", "-movflags", "+faststart",
        output
    ]
    return cmd

# ============================================================
# BUILD ALL SEGMENTS
# ============================================================

segments = []

# SEG 0: Title card
print("\n### Building title card ###")
run(title_segment(f"{IMG}/title-card.jpg", f"{OUT}/seg00_title.mp4", 4), "Title card")
segments.append(f"{OUT}/seg00_title.mp4")

# SEG 1: Narrator intro
print("\n### Building narrator intro ###")
run(narrator_segment(f"{AUDIO}/narrator-01-intro.mp3", f"{IMG}/title-card.jpg", f"{OUT}/seg01_intro.mp4"), "Narrator intro")
segments.append(f"{OUT}/seg01_intro.mp4")

# SEG 2: Malema freeze intro
print("\n### Building Malema intro ###")
run(freeze_intro(f"{IMG}/malema-freeze.jpg", "JULIUS MALEMA", "EFF Leader", f"{OUT}/seg02_malema_intro.mp4", 3), "Malema intro")
segments.append(f"{OUT}/seg02_malema_intro.mp4")

# SEG 3: Malema clip 1 - Colonial borders
print("\n### Building Malema clip 1 ###")
run(portrait_speaker(f"{CLIPS}/malema-01-colonial.mp4", f"{OUT}/seg03_malema1.mp4"), "Malema clip 1 - Colonial")
segments.append(f"{OUT}/seg03_malema1.mp4")

# SEG 4: Mashaba freeze intro
print("\n### Building Mashaba intro ###")
run(freeze_intro(f"{IMG}/mashaba-freeze.jpg", "HERMAN MASHABA", "ActionSA Leader", f"{OUT}/seg04_mashaba_intro.mp4", 3), "Mashaba intro")
segments.append(f"{OUT}/seg04_mashaba_intro.mp4")

# SEG 5: Mashaba clip 1 - Sovereignty
print("\n### Building Mashaba clip 1 ###")
run(portrait_speaker(f"{CLIPS}/mashaba-01-sovereign.mp4", f"{OUT}/seg05_mashaba1.mp4"), "Mashaba clip 1 - Sovereignty")
segments.append(f"{OUT}/seg05_mashaba1.mp4")

# SEG 6: Narrator - Berlin Conference
print("\n### Building narrator Berlin ###")
run(narrator_segment(f"{AUDIO}/narrator-02-berlin.mp3", f"{IMG}/title-card.jpg", f"{OUT}/seg06_berlin.mp4"), "Narrator Berlin")
segments.append(f"{OUT}/seg06_berlin.mp4")

# SEG 7: Malema clip 2 - Xenophobia
print("\n### Building Malema clip 2 ###")
run(portrait_speaker(f"{CLIPS}/malema-02-xenophobia.mp4", f"{OUT}/seg07_malema2.mp4"), "Malema clip 2 - Xenophobia")
segments.append(f"{OUT}/seg07_malema2.mp4")

# SEG 8: Mashaba clip 2 - Testing ground
print("\n### Building Mashaba clip 2 ###")
run(portrait_speaker(f"{CLIPS}/mashaba-02-testing-ground.mp4", f"{OUT}/seg08_mashaba2.mp4"), "Mashaba clip 2 - Testing ground")
segments.append(f"{OUT}/seg08_mashaba2.mp4")

# SEG 9: Narrator - Xenophobia
print("\n### Building narrator xenophobia ###")
run(narrator_segment(f"{AUDIO}/narrator-03-xenophobia.mp3", f"{IMG}/title-card.jpg", f"{OUT}/seg09_xenophobia.mp4"), "Narrator Xenophobia")
segments.append(f"{OUT}/seg09_xenophobia.mp4")

# SEG 10: Split screen (Malema top, Mashaba bottom) - use short excerpts
print("\n### Building split screen ###")
# Get ~15s from each
split_dur = 15
run([
    "ffmpeg", "-y",
    "-i", f"{CLIPS}/malema-02-xenophobia.mp4",
    "-i", f"{CLIPS}/mashaba-01-sovereign.mp4",
    "-filter_complex",
    (
        f"[0:v]trim=0:{split_dur},setpts=PTS-STARTPTS,scale={W}:{H//2}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H//2},setsar=1[top];"
        f"[1:v]trim=0:{split_dur},setpts=PTS-STARTPTS,scale={W}:{H//2}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H//2},setsar=1[bot];"
        f"[top][bot]vstack=inputs=2:shortest=1,"
        f"drawbox=x=0:y={H//2-1}:w={W}:h=3:color=white:t=fill,"
        f"drawtext=text='MALEMA':fontsize=28:fontcolor=white@0.7:x=20:y=20:shadowcolor=black:shadowx=1:shadowy=1,"
        f"drawtext=text='MASHABA':fontsize=28:fontcolor=white@0.7:x=20:y={H//2+20}:shadowcolor=black:shadowx=1:shadowy=1,"
        f"format=yuv420p[v]"
    ),
    "-map", "[v]",
    "-c:v", "libx264", "-preset", "medium", "-crf", "23",
    "-r", "30", "-t", str(split_dur),
    "-an", "-movflags", "+faststart",
    f"{OUT}/seg10_split.mp4"
], "Split screen")
segments.append(f"{OUT}/seg10_split.mp4")

# SEG 11: Malema clip 3 - DRC & minerals
print("\n### Building Malema clip 3 ###")
run(portrait_speaker(f"{CLIPS}/malema-03-drc.mp4", f"{OUT}/seg11_malema3.mp4"), "Malema clip 3 - DRC")
segments.append(f"{OUT}/seg11_malema3.mp4")

# SEG 12: Narrator - Resources
print("\n### Building narrator resources ###")
run(narrator_segment(f"{AUDIO}/narrator-04-resources.mp3", f"{IMG}/title-card.jpg", f"{OUT}/seg12_resources.mp4"), "Narrator Resources")
segments.append(f"{OUT}/seg12_resources.mp4")

# SEG 13: Narrator - Conclusion
print("\n### Building narrator conclusion ###")
run(narrator_segment(f"{AUDIO}/narrator-05-conclusion.mp3", f"{IMG}/title-card.jpg", f"{OUT}/seg13_conclusion.mp4"), "Narrator Conclusion")
segments.append(f"{OUT}/seg13_conclusion.mp4")

# SEG 14: Sources
print("\n### Building sources screen ###")
run(sources_segment(f"{OUT}/seg14_sources.mp4", 6), "Sources screen")
segments.append(f"{OUT}/seg14_sources.mp4")

# ============================================================
# CONCATENATE ALL SEGMENTS
# ============================================================
print("\n### Concatenating segments ###")

# Create concat file
concat_path = f"{OUT}/concat.txt"
with open(concat_path, "w") as f:
    for seg in segments:
        f.write(f"file '{seg}'\n")

run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_path,
    "-c:v", "libx264", "-preset", "medium", "-crf", "27",
    "-c:a", "aac", "-b:a", "128k",
    "-r", "30",
    "-movflags", "+faststart",
    f"{FINAL}/video_no_music.mp4"
], "Concatenate segments")

# ============================================================
# ADD BACKGROUND MUSIC
# ============================================================
print("\n### Adding background music ###")

# Get video duration
dur_result = subprocess.run(
    ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0",
     f"{FINAL}/video_no_music.mp4"],
    capture_output=True, text=True
)
video_dur = float(dur_result.stdout.strip())

run([
    "ffmpeg", "-y",
    "-i", f"{FINAL}/video_no_music.mp4",
    "-i", f"{AUDIO}/bg_music.m4a",
    "-filter_complex",
    (
        f"[1:a]atrim=0:{video_dur},asetpts=PTS-STARTPTS,"
        f"volume=0.18,afade=t=out:st={video_dur-3}:d=3[music];"
        f"[0:a][music]amix=inputs=2:duration=longest:dropout_transition=3,"
        f"loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
    ),
    "-map", "0:v", "-map", "[aout]",
    "-c:v", "copy",
    "-c:a", "aac", "-b:a", "128k",
    "-movflags", "+faststart",
    f"{FINAL}/open-borders-v2.mp4"
], "Final mix with music")

# Report final size
final = f"{FINAL}/open-borders-v2.mp4"
size = os.path.getsize(final) / (1024*1024)
dur_result2 = subprocess.run(
    ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", final],
    capture_output=True, text=True
)
dur2 = float(dur_result2.stdout.strip())

print(f"\n{'='*60}")
print(f"  DONE!")
print(f"  Output: {final}")
print(f"  Duration: {dur2:.1f}s ({dur2/60:.1f} min)")
print(f"  Size: {size:.1f} MB")
print(f"{'='*60}")
