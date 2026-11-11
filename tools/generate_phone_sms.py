#!/usr/bin/env python3
"""
Universal Phone SMS Extractor & Interactive HTML Dashboard Generator
===================================================================
Connect ANY Android phone via USB (with USB debugging enabled) or provide
an SMS Backup & Restore XML file.

Workflow:
1. Detects connected USB phones & checks Windows driver health
2. Installs Universal Android ADB/WinUSB drivers via pnputil if needed
3. Guides user to authorize USB debugging & RSA prompt
4. Extracts all SMS & contacts via ADB
5. Classifies messages, generates subjects, extracts amounts and OTPs
6. Generates a standalone, responsive HTML dashboard matching the
   AppService / Xperia Z Ultra enterprise UI design

Author: Antigravity AI & Bahman
"""

import os
import sys
import re
import json
import time
import argparse
import subprocess
import webbrowser
import ctypes
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Path resolution
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
PLATFORM_TOOLS_DIR = os.path.join(TOOLS_DIR, "platform-tools")
ADB_EXE = os.path.join(PLATFORM_TOOLS_DIR, "adb.exe")
INF_PATH = os.path.join(TOOLS_DIR, "usb_driver", "android_winusb.inf")
TEMPLATE_PATH = os.path.join(BASE_DIR, "bahman-sms.html")

if not os.path.exists(ADB_EXE):
    ADB_EXE = "adb"

# Common Android USB Vendor IDs
ANDROID_VIDS = {
    "04E8": "Samsung",
    "0FCE": "Sony",
    "18D1": "Google",
    "2717": "Xiaomi / Poco / Redmi",
    "12D1": "Huawei / Honor",
    "22B8": "Motorola",
    "2A70": "OnePlus",
    "22D9": "Oppo / Realme",
    "2D95": "Vivo",
    "1004": "LG",
    "0BB4": "HTC",
    "05C6": "Qualcomm",
    "0E8D": "MediaTek",
    "29A9": "Nothing Phone",
    "17EF": "Lenovo"
}


def is_admin() -> bool:
    """Check if the current process has Windows Administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_adb(args: List[str], serial: Optional[str] = None) -> Tuple[int, str, str]:
    """Execute an ADB command with optional target device serial."""
    cmd = [ADB_EXE]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return 1, "", f"ADB executable not found at '{ADB_EXE}'."


def scan_usb_hardware() -> List[Dict[str, str]]:
    """Scan Windows PnP for any connected Android phones (by VID, Class, or Name)."""
    ps_cmd = (
        'Get-PnpDevice -PresentOnly | '
        'Select-Object FriendlyName, InstanceId, Status, Class, Problem | '
        'ConvertTo-Json -Compress'
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []

        raw = json.loads(proc.stdout)
        if isinstance(raw, dict):
            raw = [raw]

        found_devices = []
        for dev in raw:
            iid = dev.get("InstanceId") or ""
            name = dev.get("FriendlyName") or ""
            cls = dev.get("Class") or ""
            prob = dev.get("Problem") or "CM_PROB_NONE"

            matched_vendor = None
            for vid, vname in ANDROID_VIDS.items():
                if f"VID_{vid}" in iid.upper():
                    matched_vendor = vname
                    break

            is_android_class = cls in ["AndroidUsbDeviceClass", "WPD", "Modem"]
            is_android_name = any(k in name.lower() for k in ["samsung", "xperia", "sony", "xiaomi", "redmi", "pixel", "huawei", "motorola", "oneplus", "android"])

            if matched_vendor or is_android_class or is_android_name:
                found_devices.append({
                    "name": name,
                    "instance_id": iid,
                    "vendor": matched_vendor or "Android Device",
                    "class": cls,
                    "problem": prob,
                    "needs_driver": (prob != "CM_PROB_NONE" and prob != "0") or cls == "UNKNOWN"
                })

        return found_devices
    except Exception:
        return []


def install_android_drivers() -> bool:
    """Install the Universal Android WinUSB driver package into Windows Driver Store."""
    if not os.path.exists(INF_PATH):
        print(f"[!] Driver INF not found at {INF_PATH}")
        return False

    print(f"\n[*] Installing Universal Android ADB / WinUSB Drivers...")
    print(f"    Driver package: {INF_PATH}")

    if is_admin():
        res = subprocess.run(["pnputil.exe", "/add-driver", INF_PATH, "/install"], capture_output=True, text=True)
        if res.returncode == 0:
            print("[+] Driver package added and installed successfully via pnputil!")
            return True
        else:
            print(f"[!] pnputil returned code {res.returncode}: {res.stdout}")
            return False
    else:
        print("[*] Requesting Windows Administrator permission to install driver...")
        ps_elevate = f'Start-Process pnputil.exe -ArgumentList "/add-driver `"{INF_PATH}`" /install" -Verb RunAs -Wait'
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_elevate], capture_output=True, text=True)
            print("[+] Driver installation requested via administrator prompt.")
            time.sleep(2)
            return True
        except Exception as e:
            print(f"[!] Failed to request elevation: {e}")
            return False


def get_adb_devices() -> List[Dict[str, str]]:
    """Query ADB for connected devices and their state."""
    code, stdout, _ = run_adb(["devices", "-l"])
    if code != 0:
        return []

    devices = []
    lines = stdout.splitlines()
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            serial = parts[0]
            state = parts[1]
            extra = " ".join(parts[2:])
            model_match = re.search(r"model:([^\s]+)", extra)
            device_match = re.search(r"device:([^\s]+)", extra)
            model = model_match.group(1) if model_match else ""
            device = device_match.group(1) if device_match else ""
            devices.append({
                "serial": serial,
                "state": state,
                "model": model,
                "device": device,
                "raw": line
            })
    return devices


def smart_device_detector() -> str:
    """
    Intelligent detector:
    1. Scans USB hardware
    2. Installs drivers if needed
    3. Guides user through enabling USB debugging & authorizing RSA key
    4. Returns target authorized device serial
    """
    print("\n[*] Initializing Smart Device Detector & USB Driver Monitor...")
    driver_install_attempted = False

    while True:
        # Step 1: Check ADB status first
        adb_devs = get_adb_devices()
        authorized = [d for d in adb_devs if d["state"] == "device"]
        unauthorized = [d for d in adb_devs if d["state"] == "unauthorized"]

        if authorized:
            if len(authorized) == 1:
                return authorized[0]["serial"]
            print("\n[?] Multiple authorized devices found. Select one:")
            for idx, d in enumerate(authorized, 1):
                print(f"  [{idx}] {d['serial']} ({d['model'] or d['device'] or 'Unknown Device'})")
            choice = input(f"Enter choice [1-{len(authorized)}]: ").strip()
            try:
                sel = int(choice) - 1
                if 0 <= sel < len(authorized):
                    return authorized[sel]["serial"]
            except ValueError:
                pass
            return authorized[0]["serial"]

        # Step 2: If detected in ADB but unauthorized
        if unauthorized:
            print("\n" + "="*72)
            print(" ⚠️  PHONE DETECTED — WAITING FOR AUTHORIZATION")
            print("="*72)
            print(" Your phone is connected, but needs your permission on screen:")
            print(" 1. Unlock your phone screen.")
            print(" 2. Look for the popup: 'Allow USB debugging?'")
            print(" 3. Check the box: 'Always allow from this computer'.")
            print(" 4. Tap 'Allow'.")
            print("="*72)
            time.sleep(2)
            continue

        # Step 3: ADB didn't see it -> Check Windows USB PnP hardware
        usb_devs = scan_usb_hardware()

        if usb_devs:
            print(f"\n[+] Detected {len(usb_devs)} Android USB device interface(s) in Windows:")
            needs_driver_devs = []
            for d in usb_devs:
                status_str = "Needs Driver" if d["needs_driver"] else "Hardware OK"
                print(f"    • {d['vendor']} - {d['name']} [{status_str}] (Class: {d['class']})")
                if d["needs_driver"]:
                    needs_driver_devs.append(d)

            # Check if any device has a driver problem
            if needs_driver_devs and not driver_install_attempted:
                print("\n[!] Detected device with missing or incomplete driver.")
                install_android_drivers()
                driver_install_attempted = True
                print("[*] Re-scanning devices after driver installation...")
                time.sleep(3)
                continue

            # Phone is connected via USB, but ADB does not see it -> USB Debugging is likely OFF
            print("\n" + "="*72)
            print(" 📱 PHONE CONNECTED — USB DEBUGGING IS OFF")
            print("="*72)
            print(" Windows sees your phone, but USB Debugging must be enabled:")
            print(" 1. On your phone, open Settings -> About phone -> Software information.")
            print(" 2. Tap 'Build number' 7 times until it says 'Developer mode is enabled'.")
            print(" 3. Go back to Settings -> Developer options.")
            print(" 4. Turn ON 'USB debugging'.")
            print(" 5. When prompted on the screen, tap 'Allow'.")
            print("="*72)

        else:
            print("\n" + "="*72)
            print(" 🔌 NO PHONE CONNECTED")
            print("="*72)
            print(" Please plug in any Android phone (Samsung, Sony, Xiaomi, Google, etc.)")
            print(" using a USB data cable.")
            print("="*72)

        ans = input("\nPress [Enter] to re-scan (or type 'install' to install drivers, 'q' to quit): ").strip().lower()
        if ans == 'q':
            sys.exit(0)
        elif ans == 'install':
            install_android_drivers()
            driver_install_attempted = True
        time.sleep(1)


def get_device_info(serial: str) -> Dict[str, str]:
    """Retrieve manufacturer, model, OS version, and friendly device name."""
    info = {"serial": serial}
    _, mfg, _ = run_adb(["shell", "getprop", "ro.product.manufacturer"], serial)
    _, model, _ = run_adb(["shell", "getprop", "ro.product.model"], serial)
    _, release, _ = run_adb(["shell", "getprop", "ro.build.version.release"], serial)
    _, name, _ = run_adb(["shell", "settings", "get", "global", "device_name"], serial)

    info["manufacturer"] = mfg.strip() or "Android"
    info["model"] = model.strip() or "Device"
    info["android_version"] = release.strip() or "Unknown"
    info["device_name"] = name.strip() if name and name.strip() and name.strip() != "null" else f"{info['manufacturer']} {info['model']}"
    return info


def normalize_phone(phone: str) -> str:
    """Normalize phone number to local 09... format for reliable contact mapping."""
    if not phone:
        return ""
    clean = re.sub(r"[\s\-\(\)\.]", "", phone)
    if clean.startswith("+98"):
        clean = "0" + clean[3:]
    elif clean.startswith("0098"):
        clean = "0" + clean[4:]
    elif clean.startswith("98") and len(clean) == 12:
        clean = "0" + clean[2:]
    return clean


def extract_contacts_adb(serial: str) -> Dict[str, str]:
    """Fetch address book contacts from the phone via ADB."""
    print("[*] Fetching contacts from device...")
    contacts = {}
    code, stdout, _ = run_adb(["shell", "content", "query", "--uri", "content://com.android.contacts/data/phones", "--projection", "display_name:data1"], serial)
    if code != 0 or not stdout:
        code, stdout, _ = run_adb(["shell", "content", "query", "--uri", "content://contacts/phones", "--projection", "display_name:number"], serial)

    if code == 0 and stdout:
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("Row:"):
                continue
            m = re.search(r"display_name=(.*?),\s*(?:data1|number)=(.*)$", line)
            if m:
                name = m.group(1).strip()
                num = normalize_phone(m.group(2).strip())
                if num and name:
                    contacts[num] = name

    print(f"[+] Loaded {len(contacts)} contact mappings from phone.")
    return contacts


def extract_sms_adb(serial: str) -> List[Dict]:
    """Fetch all SMS messages from Android telephony provider via ADB."""
    print("[*] Extracting SMS database from device (streaming via ADB)...")
    code, stdout, stderr = run_adb(["shell", "content", "query", "--uri", "content://sms", "--projection", "_id:address:body:date:type:read", "--sort", "'date DESC'"], serial)

    if code != 0 or not stdout:
        print(f"[!] Failed to read SMS directly via ADB: {stderr.strip()}")
        return []

    lines = stdout.splitlines()
    print(f"[+] Received {len(lines)} lines of raw SMS output.")

    raw_blocks = []
    current_block = []

    for line in lines:
        if re.match(r"^Row:\s*\d+\s+_id=", line):
            if current_block:
                raw_blocks.append("\n".join(current_block))
                current_block = []
        current_block.append(line)

    if current_block:
        raw_blocks.append("\n".join(current_block))

    print(f"[+] Segmented into {len(raw_blocks)} raw SMS message records.")

    messages = []
    for block in raw_blocks:
        m_start = re.match(r"^Row:\s*\d+\s+_id=(\d+),\s*address=(.*?),\s*body=(.*)$", block, re.DOTALL)
        if not m_start:
            continue
        sms_id = m_start.group(1)
        address = m_start.group(2).strip()
        rest = m_start.group(3)

        m_end = re.search(r",\s*date=(\d+),\s*type=(\d+)(?:,\s*read=(\d+))?$", rest)
        if m_end:
            date_ms = int(m_end.group(1))
            msg_type = int(m_end.group(2))
            read_status = int(m_end.group(3)) if m_end.group(3) is not None else 1
            body = rest[:m_end.start()].strip()
        else:
            date_ms = 0
            msg_type = 1
            read_status = 1
            body = rest.strip()

        messages.append({
            "id": sms_id,
            "address": address,
            "body": body,
            "timestamp": date_ms,
            "type": msg_type,
            "read": read_status
        })

    return messages


def parse_xml_backup(xml_path: str) -> List[Dict]:
    """Parse SMS from 'SMS Backup & Restore' XML file."""
    print(f"[*] Reading SMS from backup XML: {xml_path}")
    import xml.etree.ElementTree as ET
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as e:
        print(f"[!] Error parsing XML file: {e}")
        return []

    messages = []
    sms_elements = root.findall(".//sms")
    for el in sms_elements:
        sms_id = el.get("_id") or str(len(messages) + 1)
        address = el.get("address") or ""
        body = el.get("body") or ""
        date_ms = int(el.get("date") or 0)
        msg_type = int(el.get("type") or 1)
        contact_name = el.get("contact_name") or ""

        messages.append({
            "id": sms_id,
            "address": address.strip(),
            "body": body,
            "timestamp": date_ms,
            "type": msg_type,
            "read": 1,
            "_xml_contact": contact_name
        })

    print(f"[+] Loaded {len(messages)} SMS messages from XML backup.")
    return messages


def classify_message(msg: Dict, contacts: Dict[str, str]) -> Dict:
    """Classify SMS, assign categories, extract subjects, amounts, and balances."""
    address = msg["address"]
    norm_addr = normalize_phone(address)
    body = msg.get("body", "") or ""

    contact_name = contacts.get(norm_addr, "")
    if not contact_name and msg.get("_xml_contact"):
        contact_name = msg["_xml_contact"]

    sender_display = contact_name if contact_name else address

    category = "General"
    subject = "Message"
    amount = None
    balance = None

    body_lower = body.lower()
    addr_lower = address.lower()

    # Bank & Financial
    bank_keywords = {
        "بانك سامان": "Saman Bank", "بانک سامان": "Saman Bank",
        "بانك ملي": "Melli Bank", "بانک ملی": "Melli Bank",
        "بانک تجارت": "Tejarat Bank", "بانك تجارت": "Tejarat Bank",
        "بانك گردشگری": "Tourism Bank", "بانک گردشگری": "Tourism Bank",
        "بانک کشاورزی": "Keshavarzi Bank", "بانک پاسارگاد": "Pasargad Bank",
        "بانک ملت": "Mellat Bank", "بانک سپه": "Sepah Bank",
        "بانک صادرات": "Saderat Bank", "بانک شهر": "Shahr Bank",
        "بانک پارسیان": "Parsian Bank", "بلوبانک": "BluBank", "بلو": "BluBank",
        "بانک آینده": "Ayandeh Bank", "بانک رسالت": "Resalat Bank",
        "بانک رفاه": "Refah Bank", "بانک سینا": "Sina Bank",
        "دیجی‌پی": "DigiPay", "اسنپ‌پی": "SnappPay"
    }

    matched_bank = None
    for kw, bank_name in bank_keywords.items():
        if kw in body or kw.lower() in addr_lower:
            matched_bank = bank_name
            break

    if matched_bank or any(b in addr_lower for b in ["tejaratbank", "tourismbank", "bank melli", "blubank"]):
        category = "Financial / Bank"
        bank_name = matched_bank or address

        if "برداشت" in body or "انتقال:" in body or "خريد" in body or "کاهش" in body:
            tx_type = "Withdrawal / Purchase"
        elif "واریز" in body or "انتقال از" in body or "افزایش" in body:
            tx_type = "Deposit / Transfer In"
        elif "رمز" in body or "کد" in body or "ورود" in body:
            tx_type = "Bank Security / OTP"
        elif "مانده" in body or "موجودي" in body:
            tx_type = "Balance / Account Info"
        else:
            tx_type = "Bank Notification"

        amounts = re.findall(r"(\d{1,3}(?:,\d{3})+)", body)
        if amounts:
            amount = amounts[0]
            if len(amounts) > 1:
                balance = amounts[-1]

        if tx_type == "Withdrawal / Purchase" and amount:
            subject = f"{bank_name}: Spent {amount} Rls"
        elif tx_type == "Deposit / Transfer In" and amount:
            subject = f"{bank_name}: Received {amount} Rls"
        else:
            subject = f"{bank_name}: {tx_type}"

    # OTP / 2FA
    elif re.search(r"\b(otp|code|verification|رمز موقت|کد تایید|کد فعالسازی|کد ورود|رمز پویا)\b", body_lower) or "کد " in body:
        category = "Verification / OTP"
        otp_match = re.search(r"(?:کد|رمز|otp|code)[:\s]*([0-9]{4,8})\b", body, re.IGNORECASE)
        code = otp_match.group(1) if otp_match else "Code"

        service = sender_display
        for s in ["Telegram", "Google", "WhatsApp", "Snapp", "Digikala", "Divar", "Bale", "Eitaa", "Rubika", "Hamrah Aval", "Irancell"]:
            if s.lower() in body_lower or s.lower() in addr_lower:
                service = s
                break
        subject = f"{service} OTP: {code}"

    # Telecom / Operator
    elif any(op in addr_lower for op in ["irancell", "mci", "rightel", "hamrah", "missedcalls"]) or any(op in body for op in ["ایرانسل", "همراه اول", "رایتل"]):
        category = "Operator / Telecom"
        if "missedcalls" in addr_lower or "تماس" in body:
            subject = "Missed Call Alert"
        elif "اینترنت" in body or "گیگابایت" in body or "گیگ" in body:
            subject = f"{sender_display}: Internet / Data Package"
        elif "قبض" in body or "صورتحساب" in body:
            subject = f"{sender_display}: Bill / Invoice"
        else:
            subject = f"{sender_display}: Operator Announcement"

    # Service / Utility
    elif any(s in body_lower or s in addr_lower for s in ["snapp", "tapsi", "digikala", "divar", "torob", "abfa", "policefata"]):
        category = "Services & Utility"
        if "abfa" in addr_lower or "آب و فاضلاب" in body:
            subject = "Water Utility Bill (ABFA)"
        elif "policefata" in addr_lower or "پلیس فتا" in body:
            subject = "Police FATA Cyber Advisory"
        elif "snapp" in addr_lower or "اسنپ" in body:
            subject = "Snapp / Food / Delivery"
        elif "digikala" in addr_lower or "دیجی‌کالا" in body:
            subject = "Digikala Order / Promo"
        else:
            subject = f"{sender_display} Update"

    # Personal / Direct
    elif contact_name or address.startswith("+989") or address.startswith("09") or address.startswith("989"):
        category = "Personal / Direct"
        direction = "Sent to" if msg["type"] == 2 else "From"
        name_or_num = contact_name if contact_name else address
        first_words = " ".join(body.split()[:5])
        if len(first_words) > 40:
            first_words = first_words[:37] + "..."
        subject = f"{direction} {name_or_num}: \"{first_words}\""

    else:
        if "لغو" in body or "تخفیف" in body or "فروش" in body:
            category = "Promotions / Ads"
            subject = f"Promo: {' '.join(body.split()[:5])}..."
        else:
            category = "Other"
            subject = f"{sender_display}: {' '.join(body.split()[:4])}..."

    dt = datetime.fromtimestamp(msg["timestamp"] / 1000.0) if msg["timestamp"] > 0 else None
    date_str = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "Unknown"

    return {
        "id": str(msg["id"]),
        "addr": address,
        "contact": contact_name,
        "sender": sender_display,
        "body": body,
        "cat": category,
        "sub": subject,
        "amt": amount or "",
        "bal": balance or "",
        "type": msg["type"],
        "dir": "Sent" if msg["type"] == 2 else "Received",
        "ts": msg["timestamp"],
        "date": date_str
    }


def generate_html_dashboard(
    messages: List[Dict],
    device_info: Dict[str, str],
    output_html_path: str
) -> str:
    """Generate self-contained interactive HTML dashboard using bahman-sms.html as template."""
    print(f"[*] Generating dashboard for {len(messages)} messages...")

    if not os.path.exists(TEMPLATE_PATH):
        raise FileNotFoundError(f"Base template not found: {TEMPLATE_PATH}")

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    dev_name = device_info.get("device_name") or f"{device_info.get('manufacturer', '')} {device_info.get('model', 'Phone')}".strip()
    model = device_info.get("model", "Phone")
    android_ver = device_info.get("android_version", "")
    serial = device_info.get("serial", "")

    # Top contacts for sidebar
    contact_counts = {}
    for m in messages:
        if m["cat"] == "Personal / Direct" and m["contact"]:
            contact_counts[m["contact"]] = contact_counts.get(m["contact"], 0) + 1
    top_contacts = sorted(contact_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    contacts_html = ""
    for name, cnt in top_contacts:
        contacts_html += f'<li><a onclick="filterByText(\'{name}\')"><span><i class="bi bi-person-fill text-info"></i> {name}</span><span class="category-count">{cnt:,}</span></a></li>\n'
    if not contacts_html:
        contacts_html = '<li><span class="text-muted small ps-2">No contact names resolved</span></li>'

    # Embed JSON payload
    json_data = json.dumps(messages, ensure_ascii=False, separators=(',', ':'))

    # Replace in template
    html = template
    html = re.sub(r"<title>.*?</title>", f"<title>{dev_name} — SMS Intelligence &amp; Search Matrix</title>", html)
    html = re.sub(r'<h1>Bahman\'s SMS</h1>', f'<h1>{dev_name}</h1>', html)
    html = re.sub(r'<p>Intelligence &amp; Search Matrix</p>', f'<p>{model} • Android {android_ver}</p>', html)
    html = re.sub(r'<h2 class="h3 fw-bold text-white mb-2">Bahman\'s SMS Knowledge Engine</h2>', f'<h2 class="h3 fw-bold text-white mb-2">{dev_name} SMS Intelligence</h2>', html)
    html = re.sub(r'Galaxy A16 \(SM-A165F\)', f'{model}', html)

    # Replace data script tag with embedded payload
    data_replacement = f"<script>window.SMS_DATA = {json_data};</script>"
    html = html.replace('<script src="sms_data.js"></script>', data_replacement)

    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_mb = os.path.getsize(output_html_path) / (1024 * 1024)
    print(f"[+] Successfully generated: {output_html_path} ({size_mb:.2f} MB)")
    return output_html_path


def main():
    parser = argparse.ArgumentParser(description="Universal Phone SMS Extractor & Dashboard Generator")
    parser.add_argument("-s", "--serial", help="Target device ADB serial number (optional)")
    parser.add_argument("-o", "--output", help="Output HTML file path (default: <device_name>-sms.html)")
    parser.add_argument("-t", "--title", help="Custom dashboard title (optional)")
    parser.add_argument("-x", "--xml", help="Input SMS Backup & Restore XML file instead of ADB (optional)")
    parser.add_argument("--install-driver", action="store_true", help="Install universal Android WinUSB driver package and exit")
    parser.add_argument("--no-open", action="store_true", help="Do not automatically open browser when done")
    args = parser.parse_args()

    print("=" * 72)
    print("  📱 Universal Phone SMS Extractor & Dashboard Generator")
    print("=" * 72)

    if args.install_driver:
        success = install_android_drivers()
        sys.exit(0 if success else 1)

    device_info = {}
    contacts = {}
    raw_msgs = []

    if args.xml:
        if not os.path.isfile(args.xml):
            print(f"[!] XML file not found: {args.xml}")
            sys.exit(1)
        raw_msgs = parse_xml_backup(args.xml)
        device_info = {
            "serial": "XML-Backup",
            "manufacturer": "Backup",
            "model": os.path.basename(args.xml),
            "android_version": "N/A",
            "device_name": args.title or "SMS Backup"
        }
    else:
        # Step 1 & 2: Find connected device, check drivers, authorize
        serial = args.serial or smart_device_detector()
        device_info = get_device_info(serial)
        if args.title:
            device_info["device_name"] = args.title

        print(f"\n[+] Connected to: {device_info['device_name']} ({device_info['manufacturer']} {device_info['model']})")
        print(f"    Serial: {device_info['serial']} | Android OS: {device_info['android_version']}")

        # Step 3: Extract contacts & SMS
        contacts = extract_contacts_adb(serial)
        raw_msgs = extract_sms_adb(serial)

    if not raw_msgs:
        print("[!] No SMS messages found or extraction failed.")
        sys.exit(1)

    # Step 4: NLP Classification & Subject Generation
    print(f"[*] Processing and classifying {len(raw_msgs)} messages...")
    processed_msgs = [classify_message(m, contacts) for m in raw_msgs]

    # Step 5: Generate Dashboard
    if args.output:
        out_path = os.path.abspath(args.output)
    else:
        clean_name = re.sub(r"[^\w\-]", "_", device_info["device_name"].lower()).strip("_")
        out_filename = f"{clean_name}-sms.html"
        out_path = os.path.join(BASE_DIR, out_filename)

    generate_html_dashboard(processed_msgs, device_info, out_path)

    print("\n" + "=" * 72)
    print(f" [SUCCESS] Complete SMS Dashboard generated!")
    print(f" Location: {out_path}")
    print("=" * 72)

    # Step 6: Open in browser
    if not args.no_open:
        print("[*] Opening in your web browser...")
        webbrowser.open(f"file:///{out_path.replace(os.sep, '/')}")


if __name__ == "__main__":
    main()
