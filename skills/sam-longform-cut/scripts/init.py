"""Set up a working folder for one shoot. Run this first, from inside the folder.

    python3 init.py /path/to/raw_interview.mov

Makes src/ edit/ out/ assets/music/, finds ffmpeg, and points src/source.mov at
your file. Every other script in this skill runs from this folder and uses
relative paths, so nothing here depends on whose machine it is.
"""
import json, os, re, shutil, subprocess, sys

def find_ffmpeg():
    p = shutil.which('ffmpeg')
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    sys.exit("No ffmpeg. Install it, or: pip install imageio-ffmpeg")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = os.path.abspath(sys.argv[1])
    if not os.path.exists(src):
        sys.exit(f"No such file: {src}")

    for d in ('src', 'edit', 'out', 'assets/music', 'frames'):
        os.makedirs(d, exist_ok=True)

    ff = find_ffmpeg()
    open('ffpath.txt', 'w').write(ff + "\n")

    # name every output after the shoot, so nothing is called after someone else's job
    name = re.sub(r'[^A-Za-z0-9]+', '_',
                  os.path.splitext(os.path.basename(src))[0]).strip('_') or 'shoot'
    if not os.path.exists('shoot.json'):
        json.dump({'name': name, 'source': src}, open('shoot.json', 'w'), indent=2)

    # symlink so a 16 GB master is never copied. Fall back to a copy if the
    # filesystem will not take a link.
    dst = 'src/source.mov'
    if os.path.lexists(dst):
        os.remove(dst)
    try:
        os.symlink(src, dst)
        how = "linked"
    except OSError:
        shutil.copy2(src, dst)
        how = "copied"

    print("shoot  :", name)
    print("ffmpeg :", ff)
    print("source :", how, "->", src)
    print("size   :", round(os.path.getsize(src) / 1e9, 2), "GB")
    r = subprocess.run([ff, "-v", "error", "-i", dst, "-map", "0:v:0", "-frames:v", "1",
                        "-f", "null", "-"], capture_output=True, text=True)
    print("readable:", "yes" if r.returncode == 0 else "NO -> " + r.stderr.strip()[:200])
    print("\nNext: python3 transcribe.py   (ElevenLabs Scribe, see SKILL.md step 2)")
