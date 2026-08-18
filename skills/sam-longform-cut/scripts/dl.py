import boto3, os, sys, threading, time
from botocore.config import Config
KEY='podcasts/2026-08-13-tobi-group-coaching-2/Tobi Group Coaching 2.mov'
OUT='/home/user/Claude-Vault/.claude/workspace/sam-tobi-edit/src/source.mov'
s3 = boto3.client('s3', endpoint_url=os.environ['SAM_R2_ENDPOINT'],
    aws_access_key_id=os.environ['SAM_R2_ACCESS_KEY_ID'],
    aws_secret_access_key=os.environ['SAM_R2_SECRET_ACCESS_KEY'],
    config=Config(signature_version='s3v4', region_name='auto',
                  max_pool_connections=32, retries={'max_attempts':10,'mode':'adaptive'}))
B=os.environ['SAM_R2_BUCKET']
size=s3.head_object(Bucket=B,Key=KEY)['ContentLength']
print("size",size, flush=True)
CH=64*1024*1024
parts=[(i, o, min(o+CH,size)-1) for i,o in enumerate(range(0,size,CH))]
with open(OUT,'wb') as f: f.truncate(size)
done=[0]; lock=threading.Lock(); t0=time.time()
def work(q):
    c = boto3.client('s3', endpoint_url=os.environ['SAM_R2_ENDPOINT'],
        aws_access_key_id=os.environ['SAM_R2_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['SAM_R2_SECRET_ACCESS_KEY'],
        config=Config(signature_version='s3v4', region_name='auto', retries={'max_attempts':10,'mode':'adaptive'}))
    fh=open(OUT,'r+b')
    while True:
        with lock:
            if not q: break
            i,a,b = q.pop()
        for attempt in range(6):
            try:
                data=c.get_object(Bucket=B,Key=KEY,Range=f'bytes={a}-{b}')['Body'].read()
                break
            except Exception as e:
                if attempt==5: raise
                time.sleep(2**attempt)
        fh.seek(a); fh.write(data)
        with lock:
            done[0]+=len(data)
            el=time.time()-t0
            print(f"{done[0]/1e9:6.2f}/{size/1e9:.2f} GB  {done[0]/1e6/max(el,1):6.1f} MB/s  {el:6.0f}s", flush=True)
    fh.close()
q=list(parts)
ths=[threading.Thread(target=work,args=(q,)) for _ in range(12)]
[t.start() for t in ths]; [t.join() for t in ths]
print("DONE", os.path.getsize(OUT), flush=True)
