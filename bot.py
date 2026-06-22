#!/usr/bin/env python3
import os
import json
import logging
import tempfile
from datetime import datetime

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "TVOJ_TOKEN")
OWNER_ID = 6919439702

COUNTER_FILE = "counter.json"
KURS = 118

FIRMA = {
    "naziv":  "I&I Apartments",
    "adresa": "Karadjordjeva 27",
    "grad":   "Kragujevac",
    "pib":    "113846921",
    "mb":     "67128150",
    "racun":  "170-0050042877000-76",
    "izdao":  "Ivan Svetic",
}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def get_next_broj():
    godina = datetime.now().year
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE) as f:
            data = json.load(f)
    else:
        data = {}
    key = str(godina)
    broj = data.get(key, 0) + 1
    data[key] = broj
    with open(COUNTER_FILE, "w") as f:
        json.dump(data, f)
    return broj, godina

def peek_broj():
    godina = datetime.now().year
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE) as f:
            data = json.load(f)
    else:
        data = {}
    return data.get(str(godina), 0) + 1, godina

GOLD = colors.HexColor("#C9A84C")

def napravi_pdf(br_fakture, godina, klijent_naziv, datum_od, datum_do, broj_noci, cena_po_noci, output_path):
    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    bold_style = ParagraphStyle("bold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10)
    normal_style = ParagraphStyle("norm", parent=styles["Normal"], fontName="Helvetica", fontSize=10)
    ukupno_style = ParagraphStyle("ukupno", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=14, alignment=TA_RIGHT)
    ukupno_eur = broj_noci * cena_po_noci
    ukupno_rsd = ukupno_eur * KURS
    rb = br_fakture
    elements = []
    elements.append(Paragraph('<font color="#C9A84C"><b>I&amp;I APARTMENTS</b></font>', ParagraphStyle("logo", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=18, textColor=GOLD)))
    elements.append(Paragraph('<font color="#555555">KRAGUJEVAC</font>', ParagraphStyle("sub", parent=styles["Normal"], fontName="Helvetica", fontSize=9, textColor=colors.grey)))
    elements.append(Spacer(1, 0.6*cm))
    firma_text = (f"<b>{FIRMA['naziv']}</b><br/>{FIRMA['adresa']}<br/>{FIRMA['grad']}<br/>Pib:{FIRMA['pib']}<br/>MB:{FIRMA['mb']}<br/>Racun:{FIRMA['racun']}")
    header_table = Table([[Paragraph(firma_text, normal_style), Paragraph(f"<b>{klijent_naziv}</b>", normal_style)]], colWidths=[9*cm, 8*cm])
    header_table.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 0)]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.8*cm))
    elements.append(Paragraph(f"Gotovinski Racun br {rb}/{godina}", bold_style))
    elements.append(Spacer(1, 0.5*cm))
    header_row = [Paragraph("<b>R.B</b>", bold_style), Paragraph("<b>Sifra</b>", bold_style), Paragraph("<b>Naziv dobra Usluge</b>", bold_style), Paragraph("<b>Jedinica mere</b>", bold_style), Paragraph("<b>Kolicina</b>", bold_style), Paragraph("<b>Cena po noci</b>", bold_style), Paragraph("<b>Ukupna naknada</b>", bold_style)]
    data_row = [Paragraph(str(rb), normal_style), Paragraph("", normal_style), Paragraph(f"{datum_od}-{datum_do}", normal_style), Paragraph("Dan", normal_style), Paragraph(str(broj_noci), normal_style), Paragraph(f"{cena_po_noci:.0f}€", normal_style), Paragraph(f"{ukupno_eur:.2f}€ / {ukupno_rsd:,.0f} din".replace(",", "."), normal_style)]
    col_w = [1.5*cm, 1.5*cm, 3.5*cm, 2*cm, 2*cm, 2.5*cm, 3.5*cm]
    tbl = Table([header_row, data_row], colWidths=col_w, rowHeights=[1.2*cm, 1.8*cm])
    tbl.setStyle(TableStyle([("BOX", (0,0), (-1,-1), 0.8, colors.black), ("INNERGRID", (0,0), (-1,-1), 0.5, colors.black), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("FONTSIZE", (0,0), (-1,-1), 9)]))
    elements.append(tbl)
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph(f"<b>UKUPNO: {ukupno_eur:.2f}€/{ukupno_rsd:,.0f}din</b>".replace(",", "."), ukupno_style))
    elements.append(Spacer(1, 1*cm))
    potpis_table = Table([[Paragraph("<b>Izdao</b>", bold_style), Paragraph("<b>Primio</b>", bold_style)]], colWidths=[9*cm, 8*cm])
    potpis_table.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 0)]))
    elements.append(potpis_table)
    elements.append(Spacer(1, 0.3*cm))
    elements.append(Paragraph(f"<b>{FIRMA['izdao']}</b>", normal_style))
    elements.append(Paragraph(f"<b>{FIRMA['naziv']}</b>", normal_style))
    elements.append(Spacer(1, 0.2*cm))
    elements.append(HRFlowable(width=6*cm, thickness=1, color=colors.black, spaceAfter=0.1*cm))
    elements.append(Paragraph(f"<b>{FIRMA['izdao']} preduzetnik<br/>DELATNOST NOCLEZAJA NEKRETNINE<br/>I&amp;I APARTMENTS KRAGUJEVAC<br/>RACUN BR. {rb}/{godina}</b>", ParagraphStyle("pec", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.5, textColor=GOLD)))
    doc.build(elements)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 I&I Apartments - Bot za Fakture\n\nKomanda:\n/faktura NazivKlijenta DatumOd DatumDo BrojNoci CenaPoNoci mail\n\nPrimjer:\n/faktura Yanfeng_International 29.05.2026 12.06.2026 14 30 mail@firma.com\n\nPDF ces dobiti ovdje u Telegram.")

async def faktura_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if len(args) != 6:
        await update.message.reply_text("Pogresan format!\n/faktura NazivKlijenta DatumOd DatumDo BrojNoci CenaPoNoci mail")
        return
    klijent_naziv = args[0].replace("_", " ")
    datum_od = args[1]
    datum_do = args[2]
    to_email = args[5]
    try:
        broj_noci = int(args[3])
        cena_po_noci = float(args[4])
    except ValueError:
        await update.message.reply_text("Broj noci i cijena moraju biti brojevi!")
        return
    await update.message.reply_text("⏳ Generisem fakturu...")
    try:
        br_fakture, godina = get_next_broj()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            pdf_path = tmp.name
        napravi_pdf(br_fakture, godina, klijent_naziv, datum_od, datum_do, broj_noci, cena_po_noci, pdf_path)
        ukupno = broj_noci * cena_po_noci
        caption = (
            f"✅ Faktura {br_fakture}/{godina}\n\n"
            f"👤 Klijent: {klijent_naziv}\n"
            f"📅 {datum_od} - {datum_do} ({broj_noci} noci)\n"
            f"💶 {ukupno:.0f}€ / {ukupno*KURS:,.0f} din\n"
            f"📧 Za: {to_email}"
        )
        await ctx.bot.send_document(
            chat_id=OWNER_ID,
            document=open(pdf_path, "rb"),
            filename=f"Faktura_{br_fakture}_{godina}.pdf",
            caption=caption
        )
        await update.message.reply_text(f"✅ Faktura {br_fakture}/{godina} generisana i poslata tebi u Telegram!\nProslijedi klijentu: {to_email}")
        os.unlink(pdf_path)
    except Exception as e:
        log.exception("Greska")
        await update.message.reply_text(f"❌ Greska: {e}")

async def status_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    br, god = peek_broj()
    await update.message.reply_text(f"Sljedeca faktura: {br}/{god}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("faktura", faktura_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    log.info("Bot pokrenut...")
    app.run_polling()

if __name__ == "__main__":
    main()
