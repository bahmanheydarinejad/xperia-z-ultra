import os
import tarfile
import urllib.request
import re
from pathlib import Path

BASE_MAIN = "http://dl-cdn.alpinelinux.org/alpine/v3.20/main/armv7"
BASE_COMMUNITY = "http://dl-cdn.alpinelinux.org/alpine/v3.20/community/armv7"

OUTPUT_DIR = Path("downloads/packages")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_PACKAGES = [
    # Screen & Touch
    "fbset",
    "evtest",
    # Wi-Fi
    "wpa_supplicant",
    "wireless-tools",
    # Bluetooth
    "bluez",
    "bluez-deprecated",
    "dbus",
    # Cellular GPRS/LTE
    "libqmi",
    "libqmi-utils",
    # NFC
    "libnfc",
    "libnfc-examples",
    # Sensors / I2C
    "i2c-tools",
    # App Runtime
    "python3",
    "py3-pip",
    "py3-evdev",
]

def fetch_index(base_url, name):
    idx_path = OUTPUT_DIR / f"APKINDEX_{name}.tar.gz"
    url = f"{base_url}/APKINDEX.tar.gz"
    print(f"[*] Fetching {name} index: {url}...")
    urllib.request.urlretrieve(url, idx_path)
    
    packages = {}
    with tarfile.open(idx_path, "r:gz") as tar:
        f = tar.extractfile("APKINDEX")
        content = f.read().decode("utf-8", errors="ignore")
        
        blocks = content.split("\n\n")
        for b in blocks:
            pkg_data = {}
            for line in b.strip().split("\n"):
                if line.startswith("P:"):
                    pkg_data["pkg"] = line[2:].strip()
                elif line.startswith("V:"):
                    pkg_data["ver"] = line[2:].strip()
                elif line.startswith("D:"):
                    pkg_data["deps"] = line[2:].strip().split()
                elif line.startswith("p:"):
                    pkg_data["provides"] = line[2:].strip().split()
            if "pkg" in pkg_data and "ver" in pkg_data:
                pkg_data["repo_url"] = base_url
                pkg_data["filename"] = f"{pkg_data['pkg']}-{pkg_data['ver']}.apk"
                packages[pkg_data["pkg"]] = pkg_data
    return packages

def resolve_deps(targets, all_pkgs):
    resolved = set()
    to_visit = list(targets)
    
    while to_visit:
        pkg_name = to_visit.pop(0)
        # Strip version constraints like so:libssl.so.3 or pkg>=1.0
        clean_name = re.split(r'[<>=~]', pkg_name)[0].strip()
        if clean_name.startswith("so:") or clean_name.startswith("cmd:"):
            # Virtual provider, find matching pkg
            found = False
            for p, data in all_pkgs.items():
                if any(prov.startswith(clean_name) for prov in data.get("provides", [])):
                    clean_name = p
                    found = True
                    break
            if not found:
                continue

        if clean_name in resolved:
            continue
        
        if clean_name in all_pkgs:
            resolved.add(clean_name)
            for dep in all_pkgs[clean_name].get("deps", []):
                dep_clean = re.split(r'[<>=~]', dep)[0].strip()
                if dep_clean not in resolved and dep_clean not in to_visit:
                    to_visit.append(dep)
        else:
            # Check virtual providers
            for p, data in all_pkgs.items():
                if any(prov.split("=")[0] == clean_name for prov in data.get("provides", [])):
                    if p not in resolved and p not in to_visit:
                        to_visit.append(p)
    return resolved

def main():
    main_pkgs = fetch_index(BASE_MAIN, "main")
    comm_pkgs = fetch_index(BASE_COMMUNITY, "community")
    
    all_pkgs = {**main_pkgs, **comm_pkgs}
    print(f"[+] Total distinct packages indexed: {len(all_pkgs)}")
    
    to_download = resolve_deps(TARGET_PACKAGES, all_pkgs)
    print(f"[+] Resolved {len(to_download)} total package dependencies for all 7 hardware subsystems.")
    
    downloaded = 0
    for pkg_name in sorted(to_download):
        data = all_pkgs[pkg_name]
        filename = data["filename"]
        out_file = OUTPUT_DIR / filename
        if out_file.exists():
            continue
        url = f"{data['repo_url']}/{filename}"
        print(f"  -> Downloading {filename}...")
        try:
            urllib.request.urlretrieve(url, out_file)
            downloaded += 1
        except Exception as e:
            print(f"  [!] Failed downloading {filename}: {e}")
            
    print(f"[+] Finished! Downloaded {downloaded} new packages into {OUTPUT_DIR}.")

if __name__ == "__main__":
    main()
