"""Per-shoot names, resolved once so no script hardcodes a filename.

init.py writes shoot.json. Everything else reads it through here.
"""
import glob, json, os

_D = {}
if os.path.exists('shoot.json'):
    _D = json.load(open('shoot.json'))

NAME = _D.get('name') or 'shoot'

def transcript():
    """Word-level transcript JSON. Explicit in shoot.json, else the one in meta/."""
    p = _D.get('transcript')
    if p:
        return p
    hits = sorted(glob.glob('meta/*.json'))
    if not hits:
        raise SystemExit("No transcript. Run the transcribe step, see SKILL.md step 2.")
    if len(hits) > 1:
        raise SystemExit(f"Several transcripts in meta/, name one in shoot.json: {hits}")
    return hits[0]

def out(kind, version):
    """out/<NAME>_TRAILER_v3.mp4 and friends."""
    return f"out/{NAME}_{kind.upper()}_v{version}.mp4"
