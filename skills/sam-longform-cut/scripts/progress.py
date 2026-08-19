import json, glob, os, time
cut=json.load(open('edit/cut.json'))
S=cut['segments']
done=[i for i in range(len(S)) if os.path.exists(f"edit/segs/seg_{i:04d}.mp4.stamp")]
fr=sum(S[i]['f1']-S[i]['f0'] for i in done)
tot=cut['total_frames']
try: t0=os.path.getmtime('render_long.log')
except: t0=time.time()
start=min([os.path.getctime(f) for f in glob.glob('edit/segs/*.mp4')] or [time.time()])
el=time.time()-start
rate=fr/el if el>0 else 0
print(f"{len(done)}/{len(S)} segs  {fr}/{tot} frames ({100*fr/tot:.1f}%)  {rate:.1f} fps  eta {(tot-fr)/max(rate,0.1)/60:.0f} min")
