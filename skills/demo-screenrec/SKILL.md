---
name: demo-screenrec
description: >
  Build a crisp, zoomed software demo from a studio talking-head. You record yourself talking about
  a product (a web app, a docs page, a Mac app); this skill goes and gets the REAL interface, drives
  it with a scripted cursor, films it on a macOS-style desktop stage with the presenter as a floating
  window card, and adds the camera grammar of a top-tier tech review: 3D-tilted wide shots, smooth
  2.4x pushes on every click, typing zooms, chapter pills. Use whenever someone says "make the demo",
  "screen record this product", "show the app while I talk", "recreate the interface", "zoom in on
  the UI", or hands over studio footage plus a product name.
---

# demo-screenrec: software demos from a talking head

You never screen record. You talk to camera about the tool, and this skill builds the demo around
your words in three layers:

1. **Capture** the real interface at 2x with a scripted cursor (a web page, a docs site, an
   Electron app such as Obsidian, or a live page driven from a cloud sandbox).
2. **Stage** it: wallpaper, window cards with shadows, the presenter card, a rendered cursor, all on
   a 3840x2400 canvas.
3. **Film** the canvas with a 3D camera driven by keyframes derived from the cursor's actions.

Output: 1920x1080, 25 fps, h264, the studio audio muxed in, frame-exact (no drift).

## Install

```bash
pip install opencv-python-headless numpy pillow playwright
python -m playwright install chromium
```

`ffmpeg` and `ffprobe` must be on the PATH (`brew install ffmpeg` on a Mac). Fonts ship in
`assets/fonts/`. For a wallpaper either copy any image to `assets/wallpaper.png` or run
`python scripts/make_wallpaper.py assets/wallpaper.png`.

Optional: `boto3` if you upload renders to S3 or R2. Nothing in the skill needs it.

## Before you start

- Studio footage plus a word-level transcript (ElevenLabs Scribe is best; any word-timed transcript
  works). The transcript picks the segment and the moments where the product is on screen.
- Know what the viewer must see for each sentence: which page, which click, which scroll.

## The style bible (1080p numbers)

Treat these as locked. Change them only when the person you are cutting for asks.

**Stage**
- Real desktop look: wallpaper, windows with real title bars. The presenter is a borderless window
  card, 16:9, corner radius ~12 px when small, no border, soft shadow (blur 60, offset y 15, alpha 0.4).
- Two presenter sizes, both the SAME card, only the camera changes: small ≈ 23% of frame width
  beside or below the app window; "full" = camera pushed onto the card so it fills ~86% of the
  width with wallpaper showing round it.
- App windows: real windows with real title bars, radius ~12 px, same shadow. Typical wide shot:
  window at 35-45% of the frame width on the left, presenter right or bottom-right.
- Cursor is the system arrow, drawn crisp at any zoom.

**Camera grammar**
- Wide shot when a window opens: whole layout, desktop tilted (rotY -9°, rotX 3.5°, the side away
  from the presenter comes forward), slow push 2-3% while holding.
- Every click, hover or highlighted line: push to ~2.4x centred on the point, 0.9 s, power2.inOut,
  arriving ~0.2 s after the click. Hold at least 1.5 s. Slight tilt kept (rotY -4°).
- Typing: ~1.9x on the field, straight on, for the whole typing run.
- Scrolling right after a push stays pushed in. A scroll from wide goes to 1.35x on the window.
- Nothing for 2.6 s: back to wide (1.0 s). Window closes: back to the presenter.
- Presenter only: the "full" framing above with a 2-3° tilt and a slow push.
- Cuts, not moves, between unrelated layouts. Never a whip. Never a zoom past 3.2x.

**Labels (HUD, drawn after the camera, never tilted)**
- Chapter pill: `#7 – SIRI AI` style. Montserrat ExtraBold 46 px, white, uppercase, on a navy pill
  (#141a34 at 85%, radius 16, padding 26/13), centred, baseline at 88.5% height, 0.25 s fade with a
  12 px rise, on screen ~4 s. Use it for the product or feature name.
- Source label: Montserrat ExtraBold 22 px black uppercase, top-left, on plates only.
- Nothing else floats over the picture.

**Sound** is not in this skill. Add music at the mux stage with your own rules.

## Pipeline

```
scripts/
  capture_web.py       deterministic 2x capture of a web page from a step list (Playwright)
  capture_mac.py       the same DSL on a real Mac desktop (Quartz events + screencapture -v)
  capture_sandbox.mjs  the step DSL in Node for a cloud sandbox with a live browser
  beats.py             auto camera from the action logs (the grammar above)
  stage.py             compositor + 3D camera renderer (OpenCV, ffmpeg pipe)
  build.py             one command: cut studio -> capture -> camera -> render -> mux (--chunks N)
  make_wallpaper.py    a soft gradient wallpaper if you have none
  common.py            easing, masks, shadows, cursor, pill, title bar, ffmpeg args
```

### 1. Pick the segment and the moments

Read the transcript. For each product mention decide: which app, which screen, which action (click
X, type Y, scroll to Z) and at what second it should be on screen. Write the project file (below).
Window `in`/`out` follow the words: the window pops in on the first mention and leaves when the
speaker moves on.

### 2. Get the interface, for real

Never typeset a fake UI. If the real thing cannot be reached, say so and show the real marketing
page or docs instead.

- **Web app or docs page:** `capture_web.py` steps. Check the URL returns 200 first. Login-walled
  pages need a session; the public product pages and docs are the honest fallback.
- **Electron app on a Mac (Obsidian, Notion, most desktop apps):** launch the app with a debug
  port and drive its real window through the same step file:
  `open -a Obsidian --args --remote-debugging-port=9223` then
  `{"cdp": "http://localhost:9223", "page": "app://obsidian.md", "viewport": [1200, 780], ...}`.
  Use `chrome: "inset"` for apps that leave the traffic-light gap themselves (Obsidian),
  `chrome: "traffic"` otherwise. Check selectors with a probe first. The app must be relaunched
  with the flag, so it briefly quits; never do this to the app hosting your Claude session.
- **Live page from a cloud sandbox with a Node Playwright:** edit the STEPS block in
  `capture_sandbox.mjs`, run it, tar the output folder and copy it to `cap/<layer id>/`; build.py
  reuses it as a `capture` layer.
- **Lift the UI from a real video (`clip` lane):** when the product cannot be driven, take a real
  screen recording and mount it: `{"clip": {"src": "ref/x.mp4", "start": 972.0, "duration": 28.0,
  "crop": [107,86,1710,994]}, "scale": 1.17, "actions": "actions.json", "cursor": false}`. The crop
  removes browser chrome; the footage's own cursor stays. A small `actions.json` with the on-screen
  clicks lets the auto camera push on them. A 1080p source goes soft past ~2x: keep zoom at 2.0-2.4.
  If the source recording already carries its own zooms, give it no actions and let the wide hold.
- **Native Mac app via the real screen:** `capture_mac.py`. Needs Screen Recording permission for
  the app running the session (System Settings > Privacy & Security).
- **A real terminal:** serve an xterm.js page locally, drive it with `type` and `press` steps, and
  replay the byte-for-byte output of the real command you ran. Escape `</` in any embedded HTML.

Step DSL (all routes): `goto`, `hold`, `move`, `hover`, `click`, `type`, `press`/`key`, `scroll`,
`eval`. Selectors are Playwright locators (`text=Scheduled`, `css=...`) on the web and Electron
routes, screen points on the Mac route. Time is virtual: one screenshot per output frame, so nothing
drops and the cursor path is known exactly.

Pages with entrance animations (`opacity: 0; animation: fadeUp ... forwards`, IntersectionObserver
`.reveal` classes) stay blank because the capture disables animations. Add this `eval` after `goto`
and after each `scroll`:

```
{"eval": "document.querySelectorAll('.reveal').forEach(e=>e.classList.add('visible'));[...document.querySelectorAll('body *')].forEach(e=>{if(getComputedStyle(e).opacity==='0'){e.style.opacity='1';e.style.transform='none'}})", "wait": 0.2}
```

### 3. Project file

```json
{
 "name": "my-demo",
 "fps": 25, "out": [1920,1080], "canvas": [3840,2400], "base_w": 3456,
 "wallpaper": "assets/wallpaper.png",
 "studio": {"src": "raw/MAIN_cam.mp4", "start": 236.55, "end": 252.45},
 "presenter": {"rect": [2600,1480,1000,562], "radius": 28},
 "layers": [
   {"id": "docs", "capture": {"steps": "steps_docs.json"},
    "pos": [300,330], "in": 1.3, "out": 13.4, "chrome": "traffic", "title": "Routines"}
 ],
 "camera": "auto",
 "hud": [{"kind": "pill", "text": "Routines", "in": 1.7, "out": 5.2}]
}
```

- Canvas 3840x2400 at 2x; `base_w` 3456 is the width shown at zoom 1, leaving margins for the
  tilt. Rects are canvas pixels. A web capture at 1100x700 CSS is a 2200x1476 card (76 px title bar).
- Layer kinds: `frames` (a capture), `video` (a screen recording or any clip), `image` (a plate).
  `chrome: traffic` adds the macOS title bar; omit it for a native recording.
- `presenter.out` makes the presenter card leave the stage (a screen-only section). A layer present
  from frame 0 never pops: the film opens on it.
- `camera: "auto"` runs `beats.py`; the result is saved to `cut/camera_auto.json`. Hand-edit and
  pass `--camera my.json` to override. Keyframe `t` is the ARRIVAL time, `dur` the move.

### 4. Build

```bash
python skills/demo-screenrec/scripts/build.py project.json                 # full
python skills/demo-screenrec/scripts/build.py project.json --preview 6     # first 6 s
python skills/demo-screenrec/scripts/build.py project.json --recapture     # redo captures
python skills/demo-screenrec/scripts/build.py project.json --chunks 4      # 4 parallel renders
```

Studio cut and its audio come from the same ffmpeg `-ss`, frame count asserted. Render speed is
about 5-10 fps at 1080p per process; `--chunks` splits on whole frames and re-encodes the join.

Environment variables (all optional): `DEMO_CHROME` (path to a Chromium binary when Playwright's
default is missing, e.g. in a cloud image), `DEMO_FONT_DISPLAY`, `DEMO_FONT_UI`.

### 5. QC before sending

- Contact sheet at 2 fps plus full frames at every keyframe arrival. Check: nothing clipped in the
  wide shot, the pushed shot lands on the thing being talked about, text is sharp.
- `ffprobe -count_frames` equals `(end-start)*25`. Audio length equals video length.

## Known limits

- Login-walled and bot-gated sites (most portals, godaddy.com, platform.openai.com from a data
  centre) cannot be captured live; use the `clip` lane with a real recording, or capture on a Mac
  that is logged in.
- No Dock or menu bar on the web route (the native route records the real ones).
- Multi-window layouts with windows overlapping the presenter card: the auto camera assumes the
  presenter sits clear of the windows.
