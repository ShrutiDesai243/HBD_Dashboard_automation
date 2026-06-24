import redis
import time
import os

r = redis.Redis(host='localhost', port=6379, db=0)

print("Monitoring started... (Ctrl+C se band karo)")
print("-" * 50)

prev = None
while True:
    pending = r.llen('celery')
    
    if prev is not None:
        diff = prev - pending
        speed = f"(-{diff} tasks/30sec)" if diff > 0 else "(koi change nahi)"
    else:
        speed = ""
    
    print(f"[{time.strftime('%H:%M:%S')}] Pending: {pending} {speed}")
    prev = pending
    time.sleep(30)