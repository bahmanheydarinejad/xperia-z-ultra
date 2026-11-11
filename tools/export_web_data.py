import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "sms_vault.db")
OUTPUT_JS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sms_data.js")

def export_js():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
    SELECT id, address, contact_name, sender_display, body, category, subject, amount, balance, type, type_str, timestamp, date_str
    FROM messages
    ORDER BY timestamp DESC
    """)
    rows = cur.fetchall()
    
    data = []
    for r in rows:
        data.append({
            "id": r["id"],
            "addr": r["address"],
            "contact": r["contact_name"] or "",
            "sender": r["sender_display"],
            "body": r["body"],
            "cat": r["category"],
            "sub": r["subject"],
            "amt": r["amount"] or "",
            "bal": r["balance"] or "",
            "type": r["type"],
            "dir": r["type_str"],
            "ts": r["timestamp"],
            "date": r["date_str"]
        })
        
    conn.close()
    
    print(f"[*] Exporting {len(data)} messages to {OUTPUT_JS}...")
    with open(OUTPUT_JS, "w", encoding="utf-8") as f:
        f.write("window.SMS_DATA = ")
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
        f.write(";\n")
        
    size_mb = os.path.getsize(OUTPUT_JS) / (1024 * 1024)
    print(f"[+] Successfully generated {OUTPUT_JS} ({size_mb:.2f} MB)")

if __name__ == "__main__":
    export_js()
