"""Wait briefly for a local API before running an integration collection."""

import time
import urllib.error
import urllib.request

for _ in range(50):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1) as response:
            if response.status == 200:
                print("API is ready.")
                break
    except (urllib.error.URLError, TimeoutError):
        time.sleep(0.1)
else:
    raise SystemExit("API did not start.")
