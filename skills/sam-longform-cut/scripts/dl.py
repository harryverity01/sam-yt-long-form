"""Optional. Pull the source off an S3-compatible bucket (Cloudflare R2) in parallel.

    python3 dl.py "podcasts/2026-08-13-my-shoot/raw.mov" src/source.mov

Only needed if the footage lives in a bucket. If you already have the file on
disk, skip this and run init.py instead.

Reads R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET from env.
"""
import os, sys, threading, time
import boto3
from botocore.config import Config

def client():
    return boto3.client(
        's3', endpoint_url=os.environ['R2_ENDPOINT'],
        aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],
        config=Config(signature_version='s3v4', region_name='auto',
                      max_pool_connections=32,
                      retries={'max_attempts': 10, 'mode': 'adaptive'}))

if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    KEY, OUT = sys.argv[1], sys.argv[2]
    THREADS = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    B = os.environ['R2_BUCKET']

    os.makedirs(os.path.dirname(OUT) or '.', exist_ok=True)
    size = client().head_object(Bucket=B, Key=KEY)['ContentLength']
    print("size", size, flush=True)

    CH = 64 * 1024 * 1024
    q = [(i, o, min(o + CH, size) - 1) for i, o in enumerate(range(0, size, CH))]
    with open(OUT, 'wb') as f:
        f.truncate(size)

    done, lock, t0 = [0], threading.Lock(), time.time()

    def work():
        c = client()
        fh = open(OUT, 'r+b')
        while True:
            with lock:
                if not q:
                    break
                _, a, b = q.pop()
            for attempt in range(6):
                try:
                    data = c.get_object(Bucket=B, Key=KEY,
                                        Range=f'bytes={a}-{b}')['Body'].read()
                    break
                except Exception:
                    if attempt == 5:
                        raise
                    time.sleep(2 ** attempt)
            fh.seek(a); fh.write(data)
            with lock:
                done[0] += len(data)
                el = time.time() - t0
                print(f"{done[0]/1e9:6.2f}/{size/1e9:.2f} GB  "
                      f"{done[0]/1e6/max(el,1):6.1f} MB/s  {el:6.0f}s", flush=True)
        fh.close()

    ths = [threading.Thread(target=work) for _ in range(THREADS)]
    [t.start() for t in ths]; [t.join() for t in ths]
    got = os.path.getsize(OUT)
    print("DONE", got, flush=True)
    if got != size:
        sys.exit(f"REFUSING: got {got} bytes, bucket says {size}")
