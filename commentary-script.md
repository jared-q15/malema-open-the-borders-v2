# Open Borders: Malema vs Mashaba — V2 Script (Portrait Debate)

## Format
- 1080x1920 (9:16 portrait)
- Target duration: ~4 minutes
- Music at 15-20% volume

## Segments

### SEGMENT 0: TITLE CARD [4s]
- fal.ai generated background (African landscape, sunset, border fence silhouette)
- Text overlay: "OPEN BORDERS" (large), "Malema vs Mashaba" (subtitle)
- Fade in from black

### SEGMENT 1: NARRATOR INTRO [12s]
**TTS narration:**
"Julius Malema wants to tear down Africa's colonial borders. Herman Mashaba says that is an invitation to anarchy. Both are responding to the same crisis: a continent where millions are displaced, resources are extracted, and the people who drew the borders never consulted a single African. But only one of them is asking the right question."

**Visual:** Ken Burns on archival map of Africa (Berlin Conference partition), slow zoom out

### SEGMENT 2: MALEMA INTRO [3s]
- Freeze frame from Malema clip (B&W, high contrast)
- Name overlay: "JULIUS MALEMA" / "EFF Leader"
- Subtle zoom in on freeze frame

### SEGMENT 3: MALEMA CLIP 1 — Colonial Borders [~25s]
**Source:** malema-original.mp4, 0:00-0:25
**Visual:** Malema speaking, blurred background overlay (portrait crop)
**Content:** "This continent of Africa must be one..." / borders imposed by colonizers

### SEGMENT 4: MASHABA INTRO [3s]
- Freeze frame from Mashaba clip (B&W, high contrast)
- Name overlay: "HERMAN MASHABA" / "ActionSA Leader"
- Subtle zoom in on freeze frame

### SEGMENT 5: MASHABA CLIP 1 — Sovereignty [~25s]
**Source:** mashaba-legal-action-malema.mkv, ~0:44-1:10
**Visual:** Mashaba speaking, blurred background overlay (portrait crop)
**Content:** "South Africa is a sovereign country with borders... why would anyone expect South Africa to be a country without borders"

### SEGMENT 6: NARRATOR 1 — Berlin Conference [18s]
**TTS narration:**
"The borders Mashaba is defending were drawn in Berlin in 1884, when Bismarck invited fourteen European powers to carve up Africa with rulers and ink. Thomas Pakenham's history of the Scramble for Africa documents how not a single African was consulted. Walter Rodney showed that colonial borders were designed for extraction, not for the people who lived between them."

**Visual:** Author photos — Pakenham book cover, Rodney book cover. Ken Burns slow pan.

### SEGMENT 7: MALEMA CLIP 2 — Xenophobia [~25s]
**Source:** malema-original.mp4, ~1:45-2:10
**Visual:** Malema speaking, blurred background (portrait crop)
**Content:** Rejection of xenophobia, solidarity with fellow Africans

### SEGMENT 8: MASHABA CLIP 2 — "Testing Ground for Anarchy" [~20s]
**Source:** mashaba-legal-action-malema.mkv, ~4:10-4:30
**Visual:** Mashaba speaking, blurred background (portrait crop)
**Content:** "Let them go and try it somewhere else... why should South Africa be a testing ground for anarchy... show me any country in Africa willing to entertain such a notion"

### SEGMENT 9: NARRATOR 2 — Xenophobia's Roots [18s]
**TTS narration:**
"Hein Marais documents how the discourse of xenophobia in South Africa mirrors the discourse of apartheid itself: the same slurs, the same logic of expulsion. The attacks happen in informal settlements, where scarcity and competition converge, where the formal system has abandoned people. Both Malema and Mashaba are right about the symptoms. Neither addresses the cause."

**Visual:** Marais book cover, township footage (Ken Burns)

### SEGMENT 10: SPLIT SCREEN — The Clash [~15s]
**Layout:** Top half (1080x960): Malema clip excerpt
**Layout:** Bottom half (1080x960): Mashaba clip excerpt
**Alternating:** Quick cuts between them, 3-4 seconds each
- Malema: "We need a borderless Africa" (from original)
- Mashaba: "I will never support this nonsense of open borders"
- Malema: "You can't say we don't want colonizers but you want borders"
- Mashaba: "One undocumented foreign national is one too many"

### SEGMENT 11: MALEMA CLIP 3 — DRC & Minerals [~25s]
**Source:** malema-original.mp4, ~3:10-3:35
**Visual:** Malema speaking, blurred background (portrait crop)
**Content:** DRC, minerals, foreign powers destabilizing

### SEGMENT 12: NARRATOR 3 — Resource Curse [20s]
**TTS narration:**
"Adam Hochschild documented how King Leopold's Congo was the template for resource extraction disguised as civilization. Michael Ross notes the DRC now produces seventy percent of the world's cobalt, but demand can be redefined overnight by chemistry decisions in Chinese battery labs. The critical minerals era, Ross argues, will be more volatile than the oil age. Frantz Fanon warned that the national bourgeoisie would simply step into the colonizer's role. The borders are a symptom. The extraction is the disease."

**Visual:** Author photos — Hochschild, Fanon book covers. Ken Burns.

### SEGMENT 13: NARRATOR CONCLUSION [15s]
**TTS narration:**
"The real question is not whether borders should be open or closed. It is who drew them, who benefits from them, and whether either of these politicians has a plan for what comes after the speech ends."

**Visual:** Slow zoom out on African map, fade to muted colors

### SEGMENT 14: SOURCES + FADE OUT [6s]
- Text on dark background:
  "Sources: Pakenham, The Scramble for Africa • Rodney, How Europe Underdeveloped Africa • Marais, South Africa Pushed to the Limit • Hochschild, King Leopold's Ghost • Fanon, The Wretched of the Earth • Ross, 'The New Resource Curse'"
- Fade to black

---

## Production Notes

### Speaker Video Treatment (Portrait)
1. Extract speaker region from landscape clip (center crop to 9:16)
2. Create blurred background: `split[original][bg];[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=25[blurred];[original]scale=1080:-2[fg];[blurred][fg]overlay=(W-w)/2:(H-h)/2`
3. Speaker is centered, blurred background fills frame

### Freeze Frame Treatment
1. Extract frame at timestamp: `ffmpeg -ss T -i clip -vframes 1 frame.png`
2. Apply B&W + contrast: `format=gray,eq=contrast=1.5:brightness=0.05`
3. Add name/title text overlay with `drawtext`
4. Slow zoom (1.05x over 3s) via `zoompan`

### Split Screen (Top/Bottom)
1. Scale each speaker clip to 1080x960
2. vstack to 1080x1920
3. Add thin divider line (white, 2px)
4. Label each half with speaker name

### Title Card (fal.ai)
- Prompt: "African landscape at sunset, barbed wire border fence in foreground, silhouette of acacia trees, cinematic, moody, warm tones, photorealistic"
- Model: flux/schnell (fast, good for backgrounds)
- Text overlay via ffmpeg drawtext

### Music
- Generate ambient track via fal.ai MusicGen
- "Atmospheric, moody, African-influenced, subtle percussion, ambient electronics, 120bpm"
- Normalize speech to -14 LUFS, mix music at 0.18 (18%)

### TTS
- ElevenLabs voice: cgSgS5uT2tn9UURLr4lD
- Model: eleven-v3
