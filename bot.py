import requests
import asyncio
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread
import os
import urllib3
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ----------- ১. ফ্লাস্ক সার্ভার -----------
app = Flask('')
@app.route('/')
def home(): return "Scanner with New Token is Online!"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    Thread(target=run).start()

# ----------- ২. কনফিগারেশন -----------
# আপনার নতুন টোকেনটি এখানে বসানো হয়েছে
BOT_TOKEN = "8699896858:AAHaqeEGjj8xfNjflGCIrHbZtbfkqCVaf8c"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
}

# ----------- ৩. ডাটা স্ক্র্যাপার (সব তথ্য সহ) -----------
def get_data(tid):
    url = f"https://billpay.sonalibank.com.bd/SevenCollege/Home/Voucher/{tid}"
    try:
        r = requests.get(url, headers=headers, timeout=15, verify=False)
        soup = BeautifulSoup(r.text, "html.parser")
        html_text = r.text
        
        d = {
            "id": tid, "college": "N/A", "name": "N/A", "mobile": "N/A", 
            "roll": "N/A", "reg": "N/A", "subject": "N/A", "year": "N/A", 
            "session": "N/A", "fee_details": "N/A", "hostel": "N/A",
            "attach_type": "N/A", "pay_for": "N/A", "amount": "0.00", "date": "N/A"
        }
        
        tds = soup.find_all("td")
        for i, td in enumerate(tds):
            txt = td.get_text(strip=True).replace(":", "")
            val = tds[i+1].get_text(strip=True) if i+1 < len(tds) else "N/A"
            
            if "Transaction Id" == txt: d["id"] = val
            elif "College" == txt: d["college"] = val
            elif "Name" == txt: d["name"] = val
            elif "Mobile" == txt: d["mobile"] = val
            elif "Roll/Reg" == txt:
                if "/" in val:
                    p = val.split("/")
                    d["roll"], d["reg"] = p[0].strip(), p[1].strip()
                else: d["roll"] = val
            elif "Subject" == txt: d["subject"] = val
            elif "Year" == txt: d["year"] = val
            elif "Session" == txt: d["session"] = val
            elif "Fee Details" == txt: d["fee_details"] = val
            elif "Hostel Name" == txt: d["hostel"] = val
            elif "Attachment Type" == txt: d["attach_type"] = val
            elif "Payment for" == txt: d["pay_for"] = val
            elif "Amount" in txt: d["amount"] = val
            elif "Date" == txt: d["date"] = val

        if d["date"] == "N/A":
            match = re.search(r'(\d{2}/\d{2}/\d{4})', html_text)
            if match: d["date"] = match.group(1)
        
        return d
    except: return None

# ----------- ৪. রেজাল্ট প্রসেসর -----------
async def process_student_results(update_or_query, data_list):
    msg_source = update_or_query.message if hasattr(update_or_query, 'message') else update_or_query
    
    final_output = "📄 <b>Payment Result Found</b>\n\n"
    phones = []
    
    for i, data in enumerate(data_list, 1):
        final_output += (
            f"📄 Result {i}\n"
            f"<pre>"
            f"Transaction Id: {data['id']}\n"
            f"College: {data['college']}\n"
            f"Name: {data['name']}\n"
            f"Mobile: {data['mobile']}\n"
            f"Roll: {data['roll']}\n"
            f"Reg: {data['reg']}\n"
            f"Subject: {data['subject']}\n"
            f"Year: {data['year']}\n"
            f"Session: {data['session']}\n"
            f"Fee Details: {data['fee_details']}\n"
            f"Hostel Name: {data['hostel']}\n"
            f"Attachment Type: {data['attach_type']}\n"
            f"Payment for: {data['pay_for']}\n"
            f"Amount(BDT): {data['amount']}\n"
            f"Date: {data['date']}"
            f"</pre>\n\n"
        )
        
        p = data["mobile"].strip()[-11:]
        if len(p) >= 11 and p not in phones:
            phones.append(p)

    keyboard = []
    for ph in phones:
        keyboard.append([
            InlineKeyboardButton("📱 WhatsApp", url=f"https://wa.me/88{ph}"),
            InlineKeyboardButton("✈️ Telegram", url=f"https://t.me/+88{ph}")
        ])
    
    await msg_source.reply_text(final_output, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)

# ----------- ৫. সার্চ ইঞ্জিন -----------
async def run_search(update_or_query, context, s_r, e_r):
    msg_source = update_or_query.message if hasattr(update_or_query, 'message') else update_or_query
    
    status_text = (
        f"⏳ <b>Processing 7 College</b>\n"
        f"🔢 Reg/Roll: {s_r}\n"
        f"📊 Found: 0\n"
        f"✅ Progress: 0/{e_r - s_r + 1}"
    )
    status_msg = await msg_source.reply_text(status_text, parse_mode="HTML")
    
    context.user_data["current_end"] = e_r
    found_students = 0
    total_range = e_r - s_r + 1
    
    for i, roll in enumerate(range(s_r, e_r + 1), 1):
        try:
            url = f"https://billpay.sonalibank.com.bd/SevenCollege/Home/Search?searchStr={roll}"
            r = requests.get(url, headers=headers, timeout=10, verify=False)
            if "Voucher" in r.text:
                ids = re.findall(r'Voucher/(\d+)', r.text)
                v_list = []
                for tid in set(ids):
                    d = get_data(tid)
                    if d and d["name"] != "N/A": v_list.append(d)
                
                if v_list:
                    student_map = {}
                    for v in v_list:
                        key = f"{v['name']}_{v['roll']}".upper()
                        if key not in student_map: student_map[key] = []
                        student_map[key].append(v)
                    
                    for key in student_map:
                        found_students += 1
                        await process_student_results(update_or_query, student_map[key])

            if i % 5 == 0 or i == total_range:
                new_status = (
                    f"⏳ <b>Processing 7 College</b>\n"
                    f"🔢 Reg/Roll: {roll}\n"
                    f"📊 Found: {found_students}\n"
                    f"✅ Progress: {i}/{total_range}"
                )
                try: await status_msg.edit_text(new_status, parse_mode="HTML")
                except: pass
            await asyncio.sleep(0.05)
        except: continue

    await status_msg.delete()
    await msg_source.reply_text(f"✅ Done!\n📊 Total Found: {found_students}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👉 Next 500?", callback_data="next_500")]]))

# ----------- হ্যান্ডলারস -----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("7 College Payment Scanner!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Start Search", callback_data="btn_ready")]]))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip()
    try:
        if "-" in t:
            s, e = map(int, t.split("-"))
            await run_search(update, context, s, e)
        else: await run_search(update, context, int(t), int(t))
    except: pass

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "btn_ready": await query.message.reply_text("🚀 রোল বা রেঞ্জ পাঠান।")
    elif query.data == "next_500":
        le = context.user_data.get("current_end", 0)
        if le > 0: await run_search(query, context, le + 1, le + 500)

if __name__ == "__main__":
    keep_alive()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("🚀 Scanner with New Token is Online!")
    application.run_polling()
