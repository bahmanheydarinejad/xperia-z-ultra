import subprocess
import re
import json
import sqlite3
import os
import sys
from datetime import datetime

ADB_PATH = os.path.join(os.path.dirname(__file__), "platform-tools", "adb.exe")
DB_PATH = os.path.join(os.path.dirname(__file__), "sms_vault.db")

def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    # Remove spaces, dashes, parentheses
    clean = re.sub(r"[\s\-\(\)]", "", phone)
    if clean.startswith("+98"):
        clean = "0" + clean[3:]
    elif clean.startswith("0098"):
        clean = "0" + clean[4:]
    return clean

def fetch_contacts():
    """Fetch contacts from phone to map phone numbers to display names."""
    print("[*] Fetching contacts from device...")
    cmd = [ADB_PATH, "shell", "content", "query", "--uri", "content://com.android.contacts/data/phones", "--projection", "display_name:data1"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    
    contacts = {}
    if proc.returncode != 0:
        print(f"[!] Warning: Failed to fetch contacts: {proc.stderr}")
        return contacts

    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith("Row:"):
            continue
        # Format: Row: 0 display_name=BABA, data1=+98 992 830 4043
        m = re.search(r"display_name=(.*?),\s*data1=(.*)$", line)
        if m:
            name = m.group(1).strip()
            num = normalize_phone(m.group(2).strip())
            if num:
                contacts[num] = name
    print(f"[+] Loaded {len(contacts)} contact mappings.")
    return contacts

def fetch_raw_sms():
    """Fetch all SMS messages from Android telephony provider."""
    print("[*] Extracting SMS from device (this may take a few seconds)...")
    cmd = [ADB_PATH, "shell", "content", "query", "--uri", "content://sms", "--projection", "_id:address:body:date:type:read", "--sort", "'date DESC'"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    
    if proc.returncode != 0:
        print(f"[!] Error reading SMS: {proc.stderr}")
        return []

    lines = proc.stdout.splitlines()
    print(f"[+] Received {len(lines)} lines of raw SMS output.")
    
    messages = []
    # Pattern to identify the start of a row: Row: \d+ _id=\d+, address=..., body=...
    # Note that body can span multiple lines until the next Row: or end
    current_msg = None
    row_pattern = re.compile(r"^Row:\s*\d+\s+_id=(\d+),\s*address=(.*?),\s*body=(.*)$")
    # Date and type usually end the row: , date=(\d+), type=(\d+), read=(\d+)
    end_pattern = re.compile(r",\s*date=(\d+),\s*type=(\d+)(?:,\s*read=(\d+))?$")
    
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

    print(f"[+] Segmented into {len(raw_blocks)} SMS blocks.")

    for block in raw_blocks:
        # Match beginning
        m_start = re.match(r"^Row:\s*\d+\s+_id=(\d+),\s*address=(.*?),\s*body=(.*)$", block, re.DOTALL)
        if not m_start:
            continue
        sms_id = m_start.group(1)
        address = m_start.group(2)
        rest = m_start.group(3)
        
        # Match end
        m_end = re.search(r",\s*date=(\d+),\s*type=(\d+)(?:,\s*read=(\d+))?$", rest)
        if m_end:
            date_ms = int(m_end.group(1))
            msg_type = int(m_end.group(2))
            read_status = int(m_end.group(3)) if m_end.group(3) is not None else 1
            body = rest[:m_end.start()].strip()
        else:
            # Fallback if date wasn't at very end
            date_ms = 0
            msg_type = 1
            read_status = 1
            body = rest.strip()
            
        messages.append({
            "id": sms_id,
            "address": address.strip(),
            "body": body,
            "timestamp": date_ms,
            "type": msg_type, # 1: received, 2: sent
            "read": read_status
        })

    return messages

def categorize_and_summarize(msg, contacts):
    address = msg["address"]
    norm_addr = normalize_phone(address)
    body = msg["body"]
    
    contact_name = contacts.get(norm_addr, "")
    sender_display = contact_name if contact_name else address
    
    # Defaults
    category = "General"
    subject = "Message"
    sub_category = ""
    amount = None
    balance = None
    
    body_lower = body.lower()
    
    # 1. Bank & Financial Detection
    bank_keywords = {
        "بانك سامان": "Saman Bank",
        "بانک سامان": "Saman Bank",
        "بانك ملي": "Melli Bank",
        "بانک ملی": "Melli Bank",
        "بانک تجارت": "Tejarat Bank",
        "بانك تجارت": "Tejarat Bank",
        "بانك گردشگری": "Tourism Bank",
        "بانک گردشگری": "Tourism Bank",
        "بانک کشاورزی": "Keshavarzi Bank",
        "بانک پاسارگاد": "Pasargad Bank",
        "بانک ملت": "Mellat Bank",
        "بانک سپه": "Sepah Bank",
        "بانک صادرات": "Saderat Bank",
        "بانک شهر": "Shahr Bank",
        "بانک پارسیان": "Parsian Bank",
        "بلوبانک": "BluBank",
        "بانک آینده": "Ayandeh Bank",
        "بانک رسالت": "Resalat Bank",
        "دیجی‌پی": "DigiPay",
        "اسنپ‌پی": "SnappPay",
        "بلو": "BluBank"
    }
    
    matched_bank = None
    for kw, bank_name in bank_keywords.items():
        if kw in body or kw.lower() in address.lower():
            matched_bank = bank_name
            break
            
    if matched_bank or "TejaratBank" in address or "TourismBank" in address or "Bank Melli" in address:
        category = "Financial / Bank"
        bank_name = matched_bank or address
        
        # Transaction Type
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
            
        # Extract amounts (e.g. 1,981,000 or 5,080,000)
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
            
    # 2. OTP / 2FA Verification Codes
    elif re.search(r"\b(otp|code|verification|رمز موقت|کد تایید|کد فعالسازی|کد ورود|رمز پویا)\b", body_lower) or "کد " in body:
        category = "Verification / OTP"
        otp_match = re.search(r"(?:کد|رمز|otp|code)[:\s]*([0-9]{4,8})\b", body, re.IGNORECASE)
        code = otp_match.group(1) if otp_match else "Code"
        
        # Identify service
        service = sender_display
        for s in ["Telegram", "Google", "Snapp", "Digikala", "Divar", "Bale", "Eitaa", "Rubika", "Hamrah Aval", "Irancell"]:
            if s.lower() in body_lower or s.lower() in address.lower():
                service = s
                break
        subject = f"{service} OTP: {code}"
        
    # 3. Telecom & Operator
    elif any(op in address.lower() for op in ["irancell", "mci", "rightel", "hamrah", "missedcalls"]) or any(op in body for op in ["ایرانسل", "همراه اول", "رایتل"]):
        category = "Operator / Telecom"
        if "MissedCalls" in address or "تماس" in body:
            subject = "Missed Call Alert"
        elif "اینترنت" in body or "گیگابایت" in body or "گیگ" in body:
            subject = f"{sender_display}: Internet / Data Package"
        elif "قبض" in body or "صورتحساب" in body:
            subject = f"{sender_display}: Bill / Invoice"
        else:
            subject = f"{sender_display}: Operator Announcement"
            
    # 4. Service / Utility / E-Commerce
    elif any(s in body_lower or s in address.lower() for s in ["snapp", "tapsi", "digikala", "divar", "torob", "abfa", "policefata"]):
        category = "Services & Utility"
        if "abfa" in address.lower() or "آب و فاضلاب" in body:
            subject = "Water Utility Bill (ABFA)"
        elif "policefata" in address.lower() or "پلیس فتا" in body:
            subject = "Police FATA Cyber Advisory"
        elif "snapp" in address.lower() or "اسنپ" in body:
            subject = "Snapp / Food / Delivery"
        elif "digikala" in address.lower() or "دیجی‌کالا" in body:
            subject = "Digikala Order / Promo"
        else:
            subject = f"{sender_display} Update"
            
    # 5. Personal / Direct Conversations
    elif contact_name or address.startswith("+989") or address.startswith("09") or address.startswith("989"):
        category = "Personal / Direct"
        direction = "Sent to" if msg["type"] == 2 else "From"
        name_or_num = contact_name if contact_name else address
        first_words = " ".join(body.split()[:5])
        if len(first_words) > 40:
            first_words = first_words[:37] + "..."
        subject = f"{direction} {name_or_num}: \"{first_words}\""
        
    else:
        # Advertising / SMS Marketing
        if "لغو" in body or "تخفیف" in body or "فروش" in body:
            category = "Promotions / Ads"
            subject = f"Promo: {' '.join(body.split()[:5])}..."
        else:
            category = "Other"
            subject = f"{sender_display}: {' '.join(body.split()[:4])}..."

    # Date formatting
    dt = datetime.fromtimestamp(msg["timestamp"] / 1000.0) if msg["timestamp"] > 0 else None
    date_str = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "Unknown"

    return {
        "id": msg["id"],
        "address": address,
        "contact_name": contact_name,
        "sender_display": sender_display,
        "body": body,
        "category": category,
        "subject": subject,
        "amount": amount,
        "balance": balance,
        "type": msg["type"], # 1: received, 2: sent
        "type_str": "Sent" if msg["type"] == 2 else "Received",
        "timestamp": msg["timestamp"],
        "date_str": date_str
    }

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        address TEXT,
        contact_name TEXT,
        sender_display TEXT,
        body TEXT,
        category TEXT,
        subject TEXT,
        amount TEXT,
        balance TEXT,
        type INTEGER,
        type_str TEXT,
        timestamp INTEGER,
        date_str TEXT
    )
    """)
    # FTS5 index for full-text search
    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
        id UNINDEXED,
        sender_display,
        category,
        subject,
        body,
        content=messages,
        content_rowid=rowid
    )
    """)
    conn.commit()
    return conn

def sync_all():
    contacts = fetch_contacts()
    raw_msgs = fetch_raw_sms()
    if not raw_msgs:
        print("[!] No SMS messages found or extraction failed.")
        return 0

    print(f"[*] Processing and classifying {len(raw_msgs)} messages...")
    conn = init_database()
    cur = conn.cursor()

    cur.execute("DELETE FROM messages")
    cur.execute("DELETE FROM messages_fts")

    rows = []
    for msg in raw_msgs:
        processed = categorize_and_summarize(msg, contacts)
        rows.append((
            processed["id"],
            processed["address"],
            processed["contact_name"],
            processed["sender_display"],
            processed["body"],
            processed["category"],
            processed["subject"],
            processed["amount"],
            processed["balance"],
            processed["type"],
            processed["type_str"],
            processed["timestamp"],
            processed["date_str"]
        ))

    cur.executemany("""
    INSERT OR REPLACE INTO messages 
    (id, address, contact_name, sender_display, body, category, subject, amount, balance, type, type_str, timestamp, date_str)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    # Rebuild FTS
    cur.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()

    print(f"[+] Successfully stored & indexed {len(rows)} messages in {DB_PATH}")
    return len(rows)

def query_messages(search_term=None, category=None, limit=20, offset=0):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    query = "SELECT id, date_str, type_str, sender_display, category, subject, body, amount, balance FROM messages WHERE 1=1"
    params = []
    
    if category:
        query += " AND category LIKE ?"
        params.append(f"%{category}%")
        
    if search_term:
        query += " AND (body LIKE ? OR subject LIKE ? OR sender_display LIKE ?)"
        term = f"%{search_term}%"
        params.extend([term, term, term])
        
    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cur.execute(query, params)
    rows = cur.fetchall()
    
    results = []
    for r in rows:
        results.append({
            "id": r[0],
            "date": r[1],
            "direction": r[2],
            "sender": r[3],
            "category": r[4],
            "subject": r[5],
            "body": r[6],
            "amount": r[7],
            "balance": r[8]
        })
        
    conn.close()
    return results

def get_summary_stats():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM messages")
    total = cur.fetchone()[0]
    
    cur.execute("SELECT category, COUNT(*) FROM messages GROUP BY category ORDER BY COUNT(*) DESC")
    categories = cur.fetchall()
    
    cur.execute("SELECT sender_display, COUNT(*) FROM messages WHERE category='Financial / Bank' GROUP BY sender_display ORDER BY COUNT(*) DESC LIMIT 8")
    top_banks = cur.fetchall()
    
    cur.execute("SELECT sender_display, COUNT(*) FROM messages WHERE category='Personal / Direct' GROUP BY sender_display ORDER BY COUNT(*) DESC LIMIT 8")
    top_personal = cur.fetchall()
    
    conn.close()
    return {
        "total_messages": total,
        "categories": categories,
        "top_banks": top_banks,
        "top_personal": top_personal
    }

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--sync":
        sync_all()
    elif len(sys.argv) > 1 and sys.argv[1] == "--stats":
        stats = get_summary_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    elif len(sys.argv) > 1 and sys.argv[1] == "--query":
        term = sys.argv[2] if len(sys.argv) > 2 else ""
        res = query_messages(search_term=term, limit=10)
        for r in res:
            print(f"[{r['date']}] ({r['category']}) {r['subject']}\n  Body: {r['body'][:120]}...\n")
    else:
        sync_all()
