import urllib.request
import os
import sys
import time

URL = "https://mpl1.androidfilehost.com/dl/AVBp77T3VkgGtCjOeK1uCg/1794378754/16385555061192787270/lineage-20.0-20231020-UNOFFICIAL-togari.zip"
OUT_PATH = os.path.join("downloads", "lineage-20.0-20231020-UNOFFICIAL-togari.zip")
PART_PATH = OUT_PATH + ".part"

os.makedirs("downloads", exist_ok=True)

print(f"[*] Starting download from {URL}")
print(f"[*] Destination: {OUT_PATH}")

req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
start_time = time.time()
with urllib.request.urlopen(req) as resp, open(PART_PATH, "wb") as out_file:
    total_size = int(resp.headers.get("Content-Length", 0))
    downloaded = 0
    chunk_size = 1024 * 1024  # 1MB
    last_print = 0

    while True:
        chunk = resp.read(chunk_size)
        if not chunk:
            break
        out_file.write(chunk)
        downloaded += len(chunk)

        now = time.time()
        if now - last_print >= 2 or downloaded == total_size:
            pct = (downloaded / total_size * 100) if total_size else 0
            mb_done = downloaded / (1024 * 1024)
            mb_tot = total_size / (1024 * 1024)
            speed = mb_done / (now - start_time) if (now - start_time) > 0 else 0
            print(f"[{pct:5.1f}%] {mb_done:.1f} MB / {mb_tot:.1f} MB ({speed:.2f} MB/s)")
            last_print = now

if os.path.exists(OUT_PATH):
    os.remove(OUT_PATH)
os.rename(PART_PATH, OUT_PATH)
print(f"[+] Download complete: {OUT_PATH} ({os.path.getsize(OUT_PATH)} bytes)")
