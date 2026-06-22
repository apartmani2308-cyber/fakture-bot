#!/usr/bin/env python3
import os
import json
import logging
import tempfile
import base64
from datetime import datetime
from io import BytesIO

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from PIL import Image as PILImage

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "TVOJ_TOKEN")
OWNER_ID = 6919439702
COUNTER_FILE = "counter.json"
KURS = 118
POCETNI_BROJ = 150

FIRMA = {
    "naziv":  "I&I Apartments",
    "adresa": "Karadjordjeva 27",
    "grad":   "Kragujevac",
    "pib":    "113846921",
    "mb":     "67128150",
    "racun":  "170-0050042877000-76",
    "izdao":  "Ivan Svetic",
}

LOGO_B64 = os.environ.get("LOGO_B64", "")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def get_logo_buf():
    if LOGO_B64:
        data = base64.b64decode(LOGO_B64)
    elif os.path.exists("logo.png"):
        with open("logo.png", "rb") as f:
            data = f.read()
    else:
        return None
    img = PILImage.open(BytesIO(data)).convert('RGBA')
    img.thumbnail((400, 160))
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

def get_next_broj():
    godina = datetime.now().year
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE) as f:
            data = json.load(f)
    else:
        data = {}
    key = str(godina)
    broj = data.get(key, POCETNI_BROJ) + 1
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
    return data.get(str(godina), POCETNI_BROJ) + 1, godina

def napravi_pdf(br_fakture, godina, klijent_naziv, datum_od, datum_do, broj_noci, cena_po_noci, output_path, valuta="EUR"):
    doc = SimpleDocTemplate(output_path, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    bold = ParagraphStyle('b', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10)
    norm = ParagraphStyle('n', parent=styles['Normal'], fontName='Helvetica', fontSize=10)
    ukupno_s = ParagraphStyle('u', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, alignment=TA_RIGHT)
    klijent_s = ParagraphStyle('kl', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leftIndent=2*cm)
    primio_s = ParagraphStyle('pr', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leftIndent=5*cm)

    ukupno_eur = broj_noci * cena_po_noci
    ukupno_rsd = ukupno_eur * KURS
    rb = br_fakture

    # Formatiranje iznosa prema valuti
    if valuta == "RSD":
        iznos_tabela = f'{int(cena_po_noci):,} din'.replace(',', '.')
        iznos_ukupno_tabela = f'{int(ukupno_eur):,} din'.replace(',', '.')
        iznos_ukupno = f'<b>UKUPNO: {int(ukupno_eur):,} din</b>'.replace(',', '.')
    else:
        iznos_tabela = f'{cena_po_noci:.0f}&#8364;'
        iznos_ukupno_tabela = f'{ukupno_eur:.2f}&#8364; / {int(ukupno_rsd):,} din'.replace(',', '.')
        iznos_ukupno = f'<b>UKUPNO: {ukupno_eur:.2f}&#8364; / {int(ukupno_rsd):,}din</b>'.replace(',', '.')

    elements = []

    # LOGO
    logo_buf = get_logo_buf()
    if logo_buf:
        logo_img = Image(logo_buf, width=6*cm, height=2.5*cm)
        logo_img.hAlign = 'LEFT'
        elements.append(logo_img)
    elements.append(Spacer(1, 0.6*cm))

    # FIRMA | KLIJENT
    firma_text = (
        f"<b>I&amp;I Apartments</b><br/>"
        f"{FIRMA['adresa']}<br/>"
        f"{FIRMA['grad']}<br/>"
        f"Pib:{FIRMA['pib']}<br/>"
        f"MB:{FIRMA['mb']}<br/>"
        f"Racun:{FIRMA['racun']}"
    )
    ht = Table([[Paragraph(firma_text, norm), Paragraph(f'<b>{klijent_naziv}</b>', klijent_s)]], colWidths=[9*cm, 8*cm])
    ht.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0)]))
    elements.append(ht)
    elements.append(Spacer(1, 0.8*cm))

    elements.append(Paragraph(f'Gotovinski Racun br {rb}/{godina}', bold))
    elements.append(Spacer(1, 0.5*cm))

    # TABELA
    hr = [Paragraph('<b>R.B</b>',bold), Paragraph('<b>Sifra</b>',bold), Paragraph('<b>Naziv dobra\nUsluge</b>',bold), Paragraph('<b>Jedinica\nmere</b>',bold), Paragraph('<b>Kolicina</b>',bold), Paragraph('<b>Cena po\nnoci</b>',bold), Paragraph('<b>Ukupna\nnaknada</b>',bold)]
    dr = [Paragraph(str(rb),norm), Paragraph('',norm), Paragraph(f'{datum_od} -\n{datum_do}',norm), Paragraph('Dan',norm), Paragraph(str(broj_noci),norm), Paragraph(iznos_tabela,norm), Paragraph(iznos_ukupno_tabela,norm)]
    cw = [1.5*cm, 1.5*cm, 3.5*cm, 2*cm, 2*cm, 2.5*cm, 3.5*cm]
    tbl = Table([hr, dr], colWidths=cw, rowHeights=[1.2*cm, 1.8*cm])
    tbl.setStyle(TableStyle([('BOX',(0,0),(-1,-1),0.8,colors.black),('INNERGRID',(0,0),(-1,-1),0.5,colors.black),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('FONTSIZE',(0,0),(-1,-1),9)]))
    elements.append(tbl)
    elements.append(Spacer(1, 0.5*cm))

    elements.append(Paragraph(iznos_ukupno, ukupno_s))
    elements.append(Spacer(1, 1.5*cm))

    # POTPIS
    potpis_blok = Table([
        [Paragraph('<b>Izdao</b>', bold),              Paragraph('<b>Primio</b>', primio_s)],
        [Paragraph('<b>Ivan Svetic</b>', norm),         Paragraph('', norm)],
        [Paragraph('<b>I&amp;I Apartments</b>', norm),  Paragraph('', norm)],
        [Spacer(1, 1.5*cm),                             Spacer(1, 1.5*cm)],
        [HRFlowable(width=6*cm, thickness=1, color=colors.black), HRFlowable(width=5*cm, thickness=1, color=colors.black)],
    ], colWidths=[9*cm, 8*cm])
    potpis_blok.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),0),
        ('RIGHTPADDING',(0,0),(-1,-1),0),
        ('TOPPADDING',(0,0),(-1,-1),2),
        ('BOTTOMPADDING',(0,0),(-1,-1),2),
        ('LEFTPADDING',(1,4),(1,4),1.5*cm),
    ]))
    elements.append(potpis_blok)
    doc.build(elements)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 I&I Apartments - Bot za Fakture\n\n"
        "Komanda:\n"
        "/faktura NazivKlijenta DatumOd DatumDo BrojNoci Cijena mail EUR\n"
        "/faktura NazivKlijenta DatumOd DatumDo BrojNoci Cijena mail RSD\n\n"
        "Primjeri:\n"
        "/faktura Yanfeng_International 29.05.2026 12.06.2026 14 30 mail@firma.com EUR\n"
        "/faktura Lokalna_Firma 29.05.2026 12.06.2026 14 3540 mail@firma.com RSD"
    )

async def faktura_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if len(args) != 7:
        await update.message.reply_text(
            "❌ Pogresan format!\n\n"
            "/faktura NazivKlijenta DatumOd DatumDo BrojNoci Cijena mail EUR\n"
            "/faktura NazivKlijenta DatumOd DatumDo BrojNoci Cijena mail RSD\n\n"
            "Primjer EUR:\n"
            "/faktura Yanfeng_Int 29.05.2026 12.06.2026 14 30 mail@firma.com EUR\n\n"
            "Primjer RSD:\n"
            "/faktura Lokalna_Firma 29.05.2026 12.06.2026 14 3540 mail@firma.rs RSD"
        )
        return

    klijent_naziv = args[0].replace("_", " ")
    datum_od = args[1]
    datum_do = args[2]
    to_email = args[5]
    valuta = args[6].upper()

    if valuta not in ["EUR", "RSD"]:
        await update.message.reply_text("❌ Valuta mora biti EUR ili RSD!")
        return

    try:
        broj_noci = int(args[3])
        cena_po_noci = float(args[4])
    except ValueError:
        await update.message.reply_text("❌ Broj noci i cijena moraju biti brojevi!")
        return

    await update.message.reply_text("⏳ Generisem fakturu...")

    try:
        br_fakture, godina = get_next_broj()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            pdf_path = tmp.name

        napravi_pdf(br_fakture, godina, klijent_naziv, datum_od, datum_do, broj_noci, cena_po_noci, pdf_path, valuta)

        ukupno = broj_noci * cena_po_noci
        if valuta == "RSD":
            iznos_caption = f"{int(ukupno):,} din".replace(",", ".")
        else:
            iznos_caption = f"{ukupno:.0f}€ / {int(ukupno*KURS):,} din".replace(",", ".")

        caption = (
            f"✅ Faktura {br_fakture}/{godina}\n\n"
            f"👤 {klijent_naziv}\n"
            f"📅 {datum_od} - {datum_do} ({broj_noci} noci)\n"
            f"💶 {iznos_caption}\n"
            f"📧 Za: {to_email}"
        )

        await ctx.bot.send_document(
            chat_id=OWNER_ID,
            document=open(pdf_path, "rb"),
            filename=f"Faktura_{br_fakture}_{godina}.pdf",
            caption=caption
        )
        await update.message.reply_text(f"✅ Faktura {br_fakture}/{godina} generisana!\nProslijedi klijentu: {to_email}")
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
