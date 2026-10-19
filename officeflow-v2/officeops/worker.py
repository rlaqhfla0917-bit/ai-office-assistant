"""Background job worker. No network requests unless REDIS_URL is explicitly set."""
from __future__ import annotations
import os
import time
from .db import init_db
from .jobs import run_one

def main():
    init_db()
    print('OfficeOps worker started; press Ctrl+C to stop.',flush=True)
    try:
        while True:
            result=run_one()
            if result:
                print(f"Job #{result['id']} → {result['status']} (attempt {result['attempts']})",flush=True)
            else:
                # The durable DB is polled, even if Redis signal was dropped.
                url=os.getenv('REDIS_URL')
                if url:
                    try:
                        import redis
                        redis.Redis.from_url(url,socket_connect_timeout=0.5,socket_timeout=2).brpop('officeops:queued',timeout=1)
                    except Exception:
                        time.sleep(float(os.getenv('WORKER_POLL_SECONDS','1')))
                else:
                    time.sleep(float(os.getenv('WORKER_POLL_SECONDS','1')))
    except KeyboardInterrupt:
        print('Worker stopped')

if __name__=='__main__': main()
