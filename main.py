import nest_asyncio
import asyncio
import re
import os
from fpdf import FPDF
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler
)

nest_asyncio.apply()

# State Percakapan
CHOOSING, INPUT_ODP, INPUT_PENYEBAB, INPUT_BA_TEXT = range(4)

# Data Gudang (Pindahan dari Excel agar bot mandiri)
DATA_GUDANG = {
    "LEMBANG": "GD244",
    "PADALARANG": "GD123",
    "CIMAHI": "GD207",
    "BANJARAN": "GD156",
    "MAJALAYA": "GD206",
    "BANDUNG": "GD08",
    "RAJAWALI": "GD0157"
}

# --- FUNGSI GENERATE PDF (MENGGANTIKAN EXCEL) ---
class BAPDF(FPDF):
    def header(self):
        self.set_font("Arial", 'B', 12)
        self.cell(0, 10, "BERITA ACARA PENGAMBILAN MATERIAL (MANUAL)", ln=True, align='C')
        self.ln(5)

def create_ba_pdf(data, materials, filename):
    pdf = BAPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    
    # Header Info
    wh_user = data.get("WH", "").upper()
    id_gudang = f"{DATA_GUDANG.get(wh_user, '')} {wh_user}"
    
    info = [
        ("Nomor", f"..../LG/TA-0203/01/{data.get('TGL', '2026')[-4:]}"),
        ("ID_Gudang", id_gudang),
        ("Tanggal", data.get("TGL", "")),
        ("Nama Project", data.get("LOKASI", "")),
        ("Nama Mitra", data.get("MITRA", "")),
    ]
    
    for label, value in info:
        pdf.cell(40, 7, label, border=0)
        pdf.cell(5, 7, ":", border=0)
        pdf.cell(0, 7, value, border=0, ln=True)
    
    pdf.ln(5)
    
    # Tabel Material
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(10, 10, "No", 1, 0, 'C')
    pdf.cell(80, 10, "Nama Barang", 1, 0, 'C')
    pdf.cell(30, 10, "Satuan", 1, 0, 'C')
    pdf.cell(30, 10, "Jml Diminta", 1, 0, 'C')
    pdf.cell(30, 10, "Jml Diberi", 1, 1, 'C')
    
    pdf.set_font("Arial", size=9)
    for i in range(12):  # Tetap 12 baris seperti di Excel
        no = i + 1
        nama = ""
        satuan = ""
        qty = ""
        
        if i < len(materials):
            m_nama, m_qty = materials[i]
            nama = m_nama
            qty = m_qty
            # Logika Satuan
            if "AC-OF-SM-ADSS" in nama.upper(): satuan = "Meter"
            elif any(x in nama.upper() for x in ["PU-S7.0-400NM", "PU-S9.0-140"]): satuan = "Batang"
            else: satuan = "Pcs"
            
        pdf.cell(10, 7, str(no), 1, 0, 'C')
        pdf.cell(80, 7, nama, 1, 0, 'L')
        pdf.cell(30, 7, satuan, 1, 0, 'C')
        pdf.cell(30, 7, qty, 1, 0, 'C')
        pdf.cell(30, 7, qty, 1, 1, 'C')

    pdf.ln(10)
    # Area Tanda Tangan (Sederhana)
    pdf.cell(95, 5, "Mengetahui/Menyetujui", 0, 0, 'C')
    pdf.cell(95, 5, "Pemohon/Peminta", 0, 1, 'C')
    pdf.ln(15)
    pdf.cell(95, 5, "ADRIAN RASYID", 0, 0, 'C')
    pdf.cell(95, 5, "YUSUF CAHYO UTOMO", 0, 1, 'C')
    
    pdf.output(filename)

# --- HANDLER TELEGRAM (SAMA SEPERTI SEBELUMNYA) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [['Input Gamas', 'BA Manual']]
    await update.message.reply_text("Pilih fitur:", reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True))
    return CHOOSING

async def start_gamas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Datek Terdampak (ODP):", reply_markup=ReplyKeyboardRemove())
    return INPUT_ODP

async def get_odp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['odp_raw'] = update.message.text
    await update.message.reply_text("Penyebab:")
    return INPUT_PENYEBAB

async def get_penyebab(update: Update, context: ContextTypes.DEFAULT_TYPE):
    odp_raw = context.user_data['odp_raw']
    odc = re.sub(r'\d', '', odp_raw.replace("ODP", "ODC").replace("/", ""))
    try: sto = odc.split("-")[1][:3]
    except: sto = "..."
    output = f"#request\nSTO : {sto}\nDatek Terdampak (ODC): {odc}\nDatek Terdampak (ODP): {odp_raw}\nPenyebab: {update.message.text}\nPIC: yusuf 08112229796"
    await update.message.reply_text(output)
    return ConversationHandler.END

async def start_ba(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kirimkan data ringkasan material:", reply_markup=ReplyKeyboardRemove())
    return INPUT_BA_TEXT

async def get_ba_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text
    data = {}
    for line in raw_text.split('\n'):
        if ':' in line:
            k, v = line.split(':', 1)
            data[k.strip().upper()] = v.strip()
            
    materials = re.findall(r'-\s*(.*?)\s*=\s*(\d+)', raw_text)
    project_name = data.get("LOKASI", "Tanpa_Project")
    safe_name = re.sub(r'[\\/*?:"<>|]', "_", project_name)
    filename = f"BA_Manual_{safe_name}.pdf"
    
    await update.message.reply_text("⏳ Generating PDF (Light Version)...")
    create_ba_pdf(data, materials, filename)
    
    with open(filename, 'rb') as doc:
        await update.message.reply_document(document=doc, filename=filename)
    os.remove(filename)
    return ConversationHandler.END

async def main():
    app = ApplicationBuilder().token("8445793972:AAEAtlfKNHy4VC5eYgnXtx0RJbJ8i53rjko").build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), MessageHandler(filters.Regex('^Input Gamas$'), start_gamas), MessageHandler(filters.Regex('^BA Manual$'), start_ba)],
        states={
            CHOOSING: [MessageHandler(filters.Regex('^Input Gamas$'), start_gamas), MessageHandler(filters.Regex('^BA Manual$'), start_ba)],
            INPUT_ODP: [MessageHandler(filters.TEXT, get_odp)],
            INPUT_PENYEBAB: [MessageHandler(filters.TEXT, get_penyebab)],
            INPUT_BA_TEXT: [MessageHandler(filters.TEXT, get_ba_text)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )
    app.add_handler(conv)
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    while True: await asyncio.sleep(1)

if __name__ == '__main__':

    asyncio.get_event_loop().create_task(main())
