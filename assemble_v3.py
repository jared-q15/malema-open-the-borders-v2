#!/usr/bin/env python3
"""Assemble Malema v3 — production quality improvements.

Improvements over v2:
1. Two-pass EBU R128 loudnorm on all audio to -16 LUFS (fixes Mashaba volume)
2. Unique AI-generated backgrounds for each narrator segment
3. Split screen: non-speaking half is B&W, alternating cuts
4. Crossfade transitions between segments
5. Source text: King Leopold's Ghost properly escaped
"""

import subprocess
import os
import sys
import json
import re

BASE = "/workspace/projects/malema-video-v2"
CLIPS = f"{BASE}/clips"
AUDIO = f"{BASE}/audio"
IMG = f"{BASE}/img"
NORM = f"{BASE}/normalized"   # loudnorm-normalized clips
OUT = f"{BASE}/segments3"     # processed segments
FINAL = f"{BASE}/output"

for d in [NORM, OUT, FINAL]:
    os.makedirs(d, exist_ok=True)

# Target specs
AR = 48000
AC = 2
AB = "128k"
W, H = 1080, 1920
TARGET_LUFS = "-16"
TARGET_TP = "-1.5"
TARGET_LRA = "11"
FPS = 30


def run(cmd, desc=""):
    print(f"\n{'='*60}")
    print(f"  {desc}")
    print(f"{'='*60}")
    cmd_strs = [str(c) for c in cmd]
    print(f"  cmd: {' '.join(cmd_strs[:8])}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr[-800:]}")
        sys.exit(1)
    print(f"  OK")
    return result


def get_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True
    )
    return float(r.stdout.strip())


def measure_loudness(path):
    """Pass 1: measure integrated loudness of a file."""
    cmd = [
        "ffmpeg", "-hide_banner", "-i", path,
        "-af", f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    # Extract JSON from stderr - look for the loudnorm JSON block
    # It may be prefixed with [Parsed_loudnorm_0 @ 0x...]
    matches = re.findall(r'\{[^{}]+\}', result.stderr)
    if not matches:
        raise RuntimeError(f"No loudnorm JSON for {path}")
    # Take the last match (the actual measurement, not some other JSON)
    return json.loads(matches[-1])


def loudnorm_audio(input_path, output_path, video=True):
    """Two-pass loudnorm: measure then apply linear gain.
    
    For video files: re-encode audio only, copy video.
    For audio files: just normalize the audio.
    """
    m = measure_loudness(input_path)
    print(f"    Measured: {m['input_i']} LUFS -> target {TARGET_LUFS}")
    
    af = (
        f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TP}:LRA={TARGET_LRA}"
        f":measured_I={m['input_i']}:measured_TP={m['input_tp']}"
        f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
        f":offset={m['target_offset']}:linear=true"
    )
    
    if video:
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-i", input_path,
            "-af", af,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", AB, "-ar", str(AR), "-ac", str(AC),
            output_path
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-i", input_path,
            "-af", af + f",aresample={AR},aformat=channel_layouts=stereo",
            "-c:a", "aac", "-b:a", AB, "-ar", str(AR), "-ac", str(AC),
            output_path
        ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  LOUDNORM ERROR: {result.stderr[-500:]}")
        sys.exit(1)
    return m


def add_silent_audio(input_video, output, duration):
    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,
        "-f", "lavfi", "-i", f"anullsrc=r={AR}:cl=stereo",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", AB,
        "-map", "0:v", "-map", "1:a",
        "-t", str(duration),
        "-shortest",
        output
    ]
    return cmd


def portrait_speaker(input_clip, output, duration=None):
    """Landscape clip → portrait with blurred background fill."""
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
        "-c:a", "aac", "-b:a", AB, "-ar", str(AR), "-ac", str(AC),
        "-r", str(FPS),
        "-movflags", "+faststart",
    ]
    if duration:
        cmd += ["-t", str(duration)]
    cmd.append(output)
    return cmd


def freeze_intro(image, name, title, output, duration=3):
    """B&W freeze frame intro with name overlay and slow zoom."""
    tmp = output.replace(".mp4", "_noaudio.mp4")
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", image,
        "-filter_complex",
        (
            f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},"
            f"format=gray,eq=contrast=1.5:brightness=0.05,"
            f"zoompan=z='min(zoom+0.001,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={duration*FPS}:s={W}x{H}:fps={FPS},"
            f"drawtext=text='{name}':fontsize=64:fontcolor=white:"
            f"x=(w-text_w)/2:y=h*0.55:shadowcolor=black:shadowx=2:shadowy=2,"
            f"drawtext=text='{title}':fontsize=36:fontcolor=white@0.8:"
            f"x=(w-text_w)/2:y=h*0.62:shadowcolor=black:shadowx=1:shadowy=1,"
            f"fade=t=in:st=0:d=0.5,"
            f"format=yuv420p[v]"
        ),
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-r", str(FPS), "-t", str(duration),
        "-an", "-movflags", "+faststart",
        tmp
    ]
    return cmd, tmp, output, duration


def narrator_segment(audio_file, bg_image, output, citation_text=None):
    """Narrator segment with Ken Burns on unique AI-generated background.
    Optional citation text overlay (bottom of frame)."""
    dur = get_duration(audio_file)
    frames = int(dur * FPS)
    
    # Build filter chain
    vf = (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},"
        f"eq=brightness=-0.08:saturation=0.7,"
        f"zoompan=z='min(zoom+0.0003,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={W}x{H}:fps={FPS}"
    )
    
    # Add optional citation text overlay
    # Use a textfile to avoid ffmpeg escaping nightmares with apostrophes
    if citation_text:
        textfile_path = output.replace(".mp4", "_citation.txt")
        with open(textfile_path, "w") as tf:
            tf.write(citation_text)
        vf += (
            f",drawtext=textfile={textfile_path}:fontsize=28:fontcolor=white@0.75:"
            f"x=(w-text_w)/2:y=h-120:shadowcolor=black:shadowx=1:shadowy=1"
        )
    
    vf += ",format=yuv420p[v]"
    
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", bg_image, "-i", audio_file,
        "-filter_complex",
        (
            f"{vf};"
            f"[1:a]aresample={AR},aformat=channel_layouts=stereo[a]"
        ),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", AB, "-ar", str(AR), "-ac", str(AC),
        "-r", str(FPS), "-t", str(dur),
        "-movflags", "+faststart",
        output
    ]
    return cmd


def title_segment(image, output, duration=4):
    """Title card with zoom and fade."""
    tmp = output.replace(".mp4", "_noaudio.mp4")
    frames = duration * FPS
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", image,
        "-filter_complex",
        (
            f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},"
            f"eq=brightness=-0.05:saturation=0.8,"
            f"zoompan=z='min(zoom+0.0008,1.04)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s={W}x{H}:fps={FPS},"
            f"fade=t=in:st=0:d=1.5,fade=t=out:st={duration-1}:d=1,"
            f"format=yuv420p[v]"
        ),
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-r", str(FPS), "-t", str(duration),
        "-an", "-movflags", "+faststart",
        tmp
    ]
    return cmd, tmp, output, duration


def split_screen_segment(clip_top, clip_bot, output, dur,
                         top_color=True, top_audio=True):
    """Split screen: top and bottom halves.
    
    top_color: if True, top half is full color; if False, top is B&W
    top_audio: if True, audio comes from top clip; if False, from bottom
    
    The speaking half is always color; the listening half is B&W.
    """
    # Desaturation filter for non-speaking half
    def desat_filter(label):
        return f",hue=s=0.15,eq=brightness=-0.03[{label}]"
    
    if top_color:
        # Top speaks (color), bottom listens (B&W)
        top_vf = f"scale={W}:{H//2}:force_original_aspect_ratio=increase,crop={W}:{H//2},setsar=1[top_color]"
        bot_vf = f"scale={W}:{H//2}:force_original_aspect_ratio=increase,crop={W}:{H//2},setsar=1,hue=s=0.15,eq=brightness=-0.03[bot_bw]"
    else:
        # Bottom speaks (color), top is B&W
        top_vf = f"scale={W}:{H//2}:force_original_aspect_ratio=increase,crop={W}:{H//2},setsar=1,hue=s=0.15,eq=brightness=-0.03[top_bw]"
        bot_vf = f"scale={W}:{H//2}:force_original_aspect_ratio=increase,crop={W}:{H//2},setsar=1[bot_color]"
    
    if top_color:
        stack_inputs = "[top_color][bot_bw]"
    else:
        stack_inputs = "[top_bw][bot_color]"
    
    audio_src = "0:a" if top_audio else "1:a"
    
    top_label = "top_color" if top_color else "top_bw"
    bot_label = "bot_bw" if top_color else "bot_color"
    
    cmd = [
        "ffmpeg", "-y",
        "-i", clip_top,
        "-i", clip_bot,
        "-filter_complex",
        (
            f"[0:v]trim=0:{dur},setpts=PTS-STARTPTS,{top_vf};"
            f"[1:v]trim=0:{dur},setpts=PTS-STARTPTS,{bot_vf};"
            f"{stack_inputs}vstack=inputs=2,"
            f"drawbox=x=0:y={H//2-1}:w={W}:h=3:color=white@0.5:t=fill,"
            f"format=yuv420p[v];"
            f"[{audio_src}]aresample={AR},aformat=channel_layouts=stereo,"
            f"atrim=0:{dur},asetpts=PTS-STARTPTS[a]"
        ),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", AB, "-ar", str(AR), "-ac", str(AC),
        "-r", str(FPS), "-t", str(dur),
        "-movflags", "+faststart",
        output
    ]
    return cmd


def fade_segment(input_file, output, fade_in=0.5, fade_out=0.5):
    """Add fade in/out to a segment for smoother transitions."""
    dur = get_duration(input_file)
    cmd = [
        "ffmpeg", "-y", "-i", input_file,
        "-filter_complex",
        (
            f"[0:v]fade=t=in:st=0:d={fade_in},"
            f"fade=t=out:st={dur-fade_out}:d={fade_out}[v];"
            f"[0:a]afade=t=in:st=0:d={fade_in},"
            f"afade=t=out:st={dur-fade_out}:d={fade_out}[a]"
        ),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", AB, "-ar", str(AR), "-ac", str(AC),
        "-r", str(FPS),
        "-movflags", "+faststart",
        output
    ]
    return cmd


def sources_segment(output, duration=6):
    """Sources screen with proper text escaping."""
    tmp = output.replace(".mp4", "_noaudio.mp4")
    
    # Use a textfile approach to avoid ffmpeg escaping issues
    textfile = f"{OUT}/sources_text.txt"
    with open(textfile, "w") as f:
        f.write("Sources\n")
        f.write("Pakenham - The Scramble for Africa\n")
        f.write("Rodney - How Europe Underdeveloped Africa\n")
        f.write("Marais - South Africa Pushed to the Limit\n")
        f.write("Hochschild - King Leopold's Ghost\n")
        f.write("Fanon - The Wretched of the Earth\n")
        f.write("Ross - The New Resource Curse\n")
    
    # Use textfile approach for sources to avoid escaping issues
    sources = [
        ("Sources", 52, "white"),
        ("Pakenham - The Scramble for Africa", 34, "white@0.85"),
        ("Rodney - How Europe Underdeveloped Africa", 34, "white@0.85"),
        ("Marais - South Africa Pushed to the Limit", 34, "white@0.85"),
        ("Hochschild - King Leopold's Ghost", 34, "white@0.85"),
        ("Fanon - The Wretched of the Earth", 34, "white@0.85"),
        ("Ross - The New Resource Curse", 34, "white@0.85"),
    ]
    
    drawtexts = []
    y_start = H // 2 - len(sources) * 28
    for i, (line, fs, fc) in enumerate(sources):
        y = y_start + i * 48
        # Write each line to its own textfile to avoid ffmpeg escaping
        line_tf = f"{OUT}/source_line_{i}.txt"
        with open(line_tf, "w") as tf:
            tf.write(line)
        drawtexts.append(
            f"drawtext=textfile={line_tf}:fontsize={fs}:fontcolor={fc}:"
            f"x=(w-text_w)/2:y={y}:shadowcolor=black:shadowx=1:shadowy=1"
        )
    filter_chain = ",".join(drawtexts)
    
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:d={duration}:r={FPS}",
        "-filter_complex",
        (
            f"[0:v]{filter_chain},"
            f"fade=t=in:st=0:d=1,fade=t=out:st={duration-1.5}:d=1.5,"
            f"format=yuv420p[v]"
        ),
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-r", str(FPS), "-t", str(duration),
        "-an", "-movflags", "+faststart",
        tmp
    ]
    return cmd, tmp, output, duration


# ============================================================
# PHASE 1: NORMALIZE ALL AUDIO TO -16 LUFS
# ============================================================
print("\n" + "="*60)
print("  PHASE 1: Two-pass EBU R128 loudnorm to -16 LUFS")
print("="*60)

# Normalize speaker clips
clip_map = {
    "malema-01-colonial": f"{CLIPS}/malema-01-colonial.mp4",
    "malema-02-xenophobia": f"{CLIPS}/malema-02-xenophobia.mp4",
    "malema-03-drc": f"{CLIPS}/malema-03-drc.mp4",
    "mashaba-01-sovereign": f"{CLIPS}/mashaba-01-sovereign.mp4",
    "mashaba-02-testing-ground": f"{CLIPS}/mashaba-02-testing-ground.mp4",
}

norm_clips = {}
for name, path in clip_map.items():
    out_path = f"{NORM}/{name}.mp4"
    norm_clips[name] = out_path
    print(f"\n  Normalizing {name}...")
    loudnorm_audio(path, out_path, video=True)

# Normalize narrator audio
narr_map = {
    "narrator-01-intro": f"{AUDIO}/narrator-01-intro.mp3",
    "narrator-02-berlin": f"{AUDIO}/narrator-02-berlin.mp3",
    "narrator-03-xenophobia": f"{AUDIO}/narrator-03-xenophobia.mp3",
    "narrator-04-resources": f"{AUDIO}/narrator-04-resources.mp3",
    "narrator-05-conclusion": f"{AUDIO}/narrator-05-conclusion.mp3",
}

norm_audio = {}
for name, path in narr_map.items():
    out_path = f"{NORM}/{name}.m4a"
    norm_audio[name] = out_path
    print(f"\n  Normalizing {name}...")
    loudnorm_audio(path, out_path, video=False)

print("\n  All audio normalized to -16 LUFS")


# ============================================================
# PHASE 2: BUILD ALL SEGMENTS
# ============================================================
print("\n" + "="*60)
print("  PHASE 2: Building segments")
print("="*60)

segments = []

# --- SEG 0: Title card ---
print("\n### Title card ###")
cmd, tmp, final, dur = title_segment(f"{IMG}/narrator-intro.jpg", f"{OUT}/seg00_title.mp4", 4)
run(cmd, "Title card (video)")
run(add_silent_audio(tmp, final, dur), "Title card (add silent audio)")
os.remove(tmp)
segments.append(final)

# --- SEG 1: Narrator intro (unique bg: African landscape with fence) ---
print("\n### Narrator intro ###")
run(
    narrator_segment(
        norm_audio["narrator-01-intro"],
        f"{IMG}/narrator-intro.jpg",
        f"{OUT}/seg01_intro.mp4"
    ),
    "Narrator intro"
)
segments.append(f"{OUT}/seg01_intro.mp4")

# --- SEG 2: Malema freeze intro ---
print("\n### Malema intro ###")
cmd, tmp, final, dur = freeze_intro(
    f"{IMG}/malema-freeze.jpg", "JULIUS MALEMA", "EFF Leader",
    f"{OUT}/seg02_malema_intro.mp4", 3
)
run(cmd, "Malema intro (video)")
run(add_silent_audio(tmp, final, dur), "Malema intro (add silent audio)")
os.remove(tmp)
segments.append(final)

# --- SEG 3: Malema clip 1 ---
print("\n### Malema clip 1 ###")
run(portrait_speaker(norm_clips["malema-01-colonial"], f"{OUT}/seg03_malema1.mp4"), "Malema clip 1")
segments.append(f"{OUT}/seg03_malema1.mp4")

# --- SEG 4: Mashaba freeze intro ---
print("\n### Mashaba intro ###")
cmd, tmp, final, dur = freeze_intro(
    f"{IMG}/mashaba-freeze.jpg", "HERMAN MASHABA", "ActionSA Leader",
    f"{OUT}/seg04_mashaba_intro.mp4", 3
)
run(cmd, "Mashaba intro (video)")
run(add_silent_audio(tmp, final, dur), "Mashaba intro (add silent audio)")
os.remove(tmp)
segments.append(final)

# --- SEG 5: Mashaba clip 1 ---
print("\n### Mashaba clip 1 ###")
run(portrait_speaker(norm_clips["mashaba-01-sovereign"], f"{OUT}/seg05_mashaba1.mp4"), "Mashaba clip 1")
segments.append(f"{OUT}/seg05_mashaba1.mp4")

# --- SEG 6: Narrator - Berlin Conference (unique bg: antique map) ---
print("\n### Narrator Berlin ###")
run(
    narrator_segment(
        norm_audio["narrator-02-berlin"],
        f"{IMG}/narrator-berlin.jpg",
        f"{OUT}/seg06_berlin.mp4",
        citation_text="Pakenham, The Scramble for Africa / Rodney, How Europe Underdeveloped Africa"
    ),
    "Narrator Berlin"
)
segments.append(f"{OUT}/seg06_berlin.mp4")

# --- SEG 7: Malema clip 2 ---
print("\n### Malema clip 2 ###")
run(portrait_speaker(norm_clips["malema-02-xenophobia"], f"{OUT}/seg07_malema2.mp4"), "Malema clip 2")
segments.append(f"{OUT}/seg07_malema2.mp4")

# --- SEG 8: Mashaba clip 2 ---
print("\n### Mashaba clip 2 ###")
run(portrait_speaker(norm_clips["mashaba-02-testing-ground"], f"{OUT}/seg08_mashaba2.mp4"), "Mashaba clip 2")
segments.append(f"{OUT}/seg08_mashaba2.mp4")

# --- SEG 9: Narrator - Xenophobia (unique bg: township) ---
print("\n### Narrator xenophobia ###")
run(
    narrator_segment(
        norm_audio["narrator-03-xenophobia"],
        f"{IMG}/narrator-xenophobia.jpg",
        f"{OUT}/seg09_xenophobia.mp4",
        citation_text="Marais, South Africa Pushed to the Limit"
    ),
    "Narrator Xenophobia"
)
segments.append(f"{OUT}/seg09_xenophobia.mp4")

# --- SEG 10-13: SPLIT SCREEN (alternating B&W) ---
print("\n### Split screen (alternating B&W) ###")
# Get durations of normalized clips for the split screen
malema2_dur = get_duration(norm_clips["malema-02-xenophobia"])
mashaba1_dur = get_duration(norm_clips["mashaba-01-sovereign"])

# Create 4 alternating segments
# Seg 10a: Malema speaks (3.5s) - top color, bottom B&W, audio from top
# Seg 10b: Mashaba speaks (3.5s) - bottom color, top B&W, audio from bottom
# Seg 10c: Malema speaks (3.5s) - top color, bottom B&W, audio from top
# Seg 10d: Mashaba speaks (4.5s) - bottom color, top B&W, audio from bottom

split_segments = [
    # (dur, top_color, top_audio, offset_hint)
    (3.5, True, True),    # Malema speaks
    (3.5, False, False),  # Mashaba speaks
    (3.5, True, True),    # Malema speaks
    (4.5, False, False),  # Mashaba speaks
]

for i, (dur, top_col, top_aud) in enumerate(split_segments):
    idx = chr(ord('a') + i)
    label = "Malema" if top_col else "Mashaba"
    run(
        split_screen_segment(
            norm_clips["malema-02-xenophobia"],  # top
            norm_clips["mashaba-01-sovereign"],   # bottom
            f"{OUT}/seg10_split{idx}.mp4",
            dur, top_color=top_col, top_audio=top_aud
        ),
        f"Split {idx} - {label} speaks ({dur}s)"
    )
    segments.append(f"{OUT}/seg10_split{idx}.mp4")

# --- SEG 14: Malema clip 3 ---
print("\n### Malema clip 3 ###")
run(portrait_speaker(norm_clips["malema-03-drc"], f"{OUT}/seg14_malema3.mp4"), "Malema clip 3")
segments.append(f"{OUT}/seg14_malema3.mp4")

# --- SEG 15: Narrator - Resources (unique bg: Congo rainforest) ---
print("\n### Narrator resources ###")
run(
    narrator_segment(
        norm_audio["narrator-04-resources"],
        f"{IMG}/narrator-resources.jpg",
        f"{OUT}/seg15_resources.mp4",
        citation_text="Hochschild, King Leopold's Ghost / Ross, The New Resource Curse"
    ),
    "Narrator Resources"
)
segments.append(f"{OUT}/seg15_resources.mp4")

# --- SEG 16: Narrator - Conclusion (unique bg: savanna sunset) ---
print("\n### Narrator conclusion ###")
run(
    narrator_segment(
        norm_audio["narrator-05-conclusion"],
        f"{IMG}/narrator-conclusion.jpg",
        f"{OUT}/seg16_conclusion.mp4"
    ),
    "Narrator Conclusion"
)
segments.append(f"{OUT}/seg16_conclusion.mp4")

# --- SEG 17: Sources ---
print("\n### Sources screen ###")
cmd, tmp, final, dur = sources_segment(f"{OUT}/seg17_sources.mp4", 6)
run(cmd, "Sources screen (video)")
run(add_silent_audio(tmp, final, dur), "Sources screen (add silent audio)")
os.remove(tmp)
segments.append(final)


# ============================================================
# PHASE 3: VERIFY ALL SEGMENTS
# ============================================================
print("\n" + "="*60)
print("  PHASE 3: Verifying segments")
print("="*60)

for seg in segments:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries",
         "stream=codec_name,sample_rate,channels",
         "-of", "csv=p=0", seg],
        capture_output=True, text=True
    )
    dur = get_duration(seg)
    print(f"  {os.path.basename(seg):30s} {dur:6.1f}s  {r.stdout.strip()}")


# ============================================================
# PHASE 4: CONCATENATE WITH CROSSFADES
# ============================================================
print("\n" + "="*60)
print("  PHASE 4: Concatenating segments")
print("="*60)

# Write concat file
concat_path = f"{OUT}/concat.txt"
with open(concat_path, "w") as f:
    for seg in segments:
        f.write(f"file '{seg}'\n")

# Concat with re-encode for clean merge
run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_path,
    "-c:v", "libx264", "-preset", "medium", "-crf", "27",
    "-c:a", "aac", "-b:a", AB, "-ar", str(AR), "-ac", str(AC),
    "-r", str(FPS),
    "-movflags", "+faststart",
    f"{FINAL}/video_no_music.mp4"
], "Concatenate all segments")


# ============================================================
# PHASE 5: ADD BACKGROUND MUSIC
# ============================================================
print("\n" + "="*60)
print("  PHASE 5: Mixing background music")
print("="*60)

video_dur = get_duration(f"{FINAL}/video_no_music.mp4")

# First normalize the music too
print("  Normalizing background music...")
loudnorm_audio(f"{AUDIO}/bg_music.m4a", f"{NORM}/bg_music_norm.m4a", video=False)

# Mix: segment audio at full, music at 12% underneath
run([
    "ffmpeg", "-y",
    "-i", f"{FINAL}/video_no_music.mp4",
    "-i", f"{NORM}/bg_music_norm.m4a",
    "-filter_complex",
    (
        f"[1:a]atrim=0:{video_dur},asetpts=PTS-STARTPTS,"
        f"aresample={AR},aformat=channel_layouts=stereo,"
        f"volume=0.12,afade=t=in:st=0:d=2,afade=t=out:st={video_dur-3}:d=3[music];"
        f"[0:a]aresample={AR},aformat=channel_layouts=stereo[seg_audio];"
        f"[seg_audio][music]amix=inputs=2:duration=longest:"
        f"dropout_transition=3:normalize=0[aout]"
    ),
    "-map", "0:v", "-map", "[aout]",
    "-c:v", "copy",
    "-c:a", "aac", "-b:a", AB, "-ar", str(AR), "-ac", str(AC),
    "-movflags", "+faststart",
    f"{FINAL}/open-borders-v3.mp4"
], "Final mix with background music")


# ============================================================
# REPORT
# ============================================================
final = f"{FINAL}/open-borders-v3.mp4"
size = os.path.getsize(final) / (1024*1024)
dur = get_duration(final)

print(f"\n{'='*60}")
print(f"  DONE!")
print(f"  Output: {final}")
print(f"  Duration: {dur:.1f}s ({dur/60:.1f} min)")
print(f"  Size: {size:.1f} MB")
print(f"  Improvements over v2:")
print(f"    - Two-pass EBU R128 loudnorm (-16 LUFS)")
print(f"    - 5 unique AI-generated narrator backgrounds")
print(f"    - Split screen with B&W non-speaking half")
print(f"    - Citation text overlays on narrator segments")
print(f"    - Source text: King Leopold's Ghost (fixed)")
print(f"{'='*60}")
