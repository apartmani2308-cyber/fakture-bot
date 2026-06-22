#!/usr/bin/env python3
"""
I&I Apartments - Telegram Bot za Fakture
Komanda: /faktura ImeKlijenta PrezimeKlijenta NazivFirme DatumOd DatumDo BrojNoci CenaPoNoci mail@klijenta.com
"""

import os
import json
import logging
import smtplib
import tempfile
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ─── KONFIGURACIJA ───────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "TVOJ_TELEGRAM_TOKEN")
GMAIL_USER     = "apartmani2308@gmail.com"
GMAIL_PASS     = os.environ.get("GMAIL_APP_PASSWORD", "TVOJA_APP_LOZINKA")

COUNTER_FILE = "counter.json"
KURS         = 118  # EUR -> RSD

# Firma podaci
FIRMA = {
    "naziv":  "I&I Apartments",
    "adresa": "Karadjordjeva 27",
    "grad":   "Kragujevac",
    "pib":    "113846921",
    "mb":     "67128150",
    "racun":  "170-0050042877000-76",
    "izdao":  "Ivan Svetić",
}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ─── BROJAČ FAKTURA ──────────────────────────────────────────────────────────
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
    """Pogledaj koji je sljedeći broj bez povećavanja."""
    godina = datetime.now().year
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE) as f:
            data = json.load(f)
    else:
        data = {}
    return data.get(str(godina), 0) + 1, godina

# ─── PDF GENERATOR ───────────────────────────────────────────────────────────
PINK = colors.HexColor("#E91E8C")
DARK = colors.HexColor("#1a1a2e")

def napravi_pdf(
    br_fakture: int,
    godina: int,
    klijent_naziv: str,
    datum_od: str,
    datum_do: str,
    broj_noci: int,
    cena_po_noci: float,
    output_path: str,
):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2*cm,
        rightMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    bold_style = ParagraphStyle("bold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10)
    normal_style = ParagraphStyle("norm", parent=styles["Normal"], fontName="Helvetica", fontSize=10)
    small_style = ParagraphStyle("small", parent=styles["Normal"], fontName="Helvetica", fontSize=9)
    pink_title = ParagraphStyle("pink", parent=styles["Normal"], fontName="Helvetica-Bold",
                                fontSize=13, textColor=PINK)
    ukupno_style = ParagraphStyle("ukupno", parent=styles["Normal"], fontName="Helvetica-Bold",
                                  fontSize=14, alignment=TA_RIGHT)

    ukupno_eur = broj_noci * cena_po_noci
    ukupno_rsd = ukupno_eur * KURS
    rb = br_fakture

    elements = []

    # ── LOGO tekst (ako nema slike) ──
    elements.append(Paragraph('<font color="#E91E8C"><b>I&amp;I APARTMENTS</b></font>', ParagraphStyle(
        "logo", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=18, textColor=PINK
    )))
    elements.append(Paragraph('<font color="#555555">KRAGUJEVAC</font>', ParagraphStyle(
        "sub", parent=styles["Normal"], fontName="Helvetica", fontSize=9, textColor=colors.grey
    )))
    elements.append(Spacer(1, 0.6*cm))

    # ── DVA STUPCA: firma | klijent ──
    firma_text = (
        f"<b>{FIRMA['naziv']}</b><br/>"
        f"{FIRMA['adresa']}<br/>"
        f"{FIRMA['grad']}<br/>"
        f"Pib:{FIRMA['pib']}<br/>"
        f"MB:{FIRMA['mb']}<br/>"
        f"Racun:{FIRMA['racun']}"
    )
    klijent_text = f"<b>{klijent_naziv}</b>"

    header_table = Table(
        [[Paragraph(firma_text, normal_style), Paragraph(klijent_text, normal_style)]],
        colWidths=[9*cm, 8*cm],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.8*cm))

    # ── NAZIV FAKTURE ──
    elements.append(Paragraph(f"Gotovinski Racun br {rb}/{godina}", bold_style))
    elements.append(Spacer(1, 0.5*cm))

    # ── TABELA STAVKI ──
    header_row = [
        Paragraph("<b>R.B</b>", bold_style),
        Paragraph("<b>Sifra</b>", bold_style),
        Paragraph("<b>Naziv dobra\nUsluge</b>", bold_style),
        Paragraph("<b>Jedinica\nmere</b>", bold_style),
        Paragraph("<b>Kolicina</b>", bold_style),
        Paragraph("<b>Cena po noci</b>", bold_style),
        Paragraph("<b>Ukupna\nnaknada</b>", bold_style),
    ]
    data_row = [
        Paragraph(str(rb), normal_style),
        Paragraph("", normal_style),
        Paragraph(f"{datum_od}-\n{datum_do}", normal_style),
        Paragraph("Dan", normal_style),
        Paragraph(str(broj_noci), normal_style),
        Paragraph(f"{cena_po_noci:.0f}\u20ac", normal_style),
        Paragraph(f"{ukupno_eur:.2f}\u20ac\n{ukupno_rsd:,.0f} din".replace(",", "."), normal_style),
    ]

    col_w = [1.5*cm, 1.5*cm, 3.5*cm, 2*cm, 2*cm, 2.5*cm, 3.5*cm]
    tbl = Table([header_row, data_row], colWidths=col_w, rowHeights=[1.2*cm, 1.8*cm])
    tbl.setStyle(TableStyle([
        ("BOX",         (0,0), (-1,-1), 0.8, colors.black),
        ("INNERGRID",   (0,0), (-1,-1), 0.5, colors.black),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("FONTNAME",    (0,0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("BACKGROUND",  (0,0), (-1, 0), colors.white),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 0.5*cm))

    # ── UKUPNO ──
    elements.append(Paragraph(
        f"<b>UKUPNO: {ukupno_eur:.2f}\u20ac/{ukupno_rsd:,.0f}din</b>".replace(",", "."),
        ukupno_style
    ))
    elements.append(Spacer(1, 1*cm))

    # ── POTPIS ──
    potpis_table = Table(
        [[Paragraph("<b>Izdao</b>", bold_style), Paragraph("<b>Primio</b>", bold_style)]],
        colWidths=[9*cm, 8*cm],
    )
    potpis_table.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
    ]))
    elements.append(potpis_table)
    elements.append(Spacer(1, 0.3*cm))

    elements.append(Paragraph(f"<b>{FIRMA['izdao']}</b>", normal_style))
    elements.append(Paragraph(f"<b>{FIRMA['naziv']}</b>", normal_style))
    elements.append(Spacer(1, 0.2*cm))
    elements.append(HRFlowable(width=6*cm, thickness=1, color=colors.black, spaceAfter=0.1*cm))
    elements.append(Paragraph(
        f"<font size=8><b>{FIRMA['izdao']} preduzetnik<br/>"
        f"DELATNOST NOCLEŻAJA NEKRETNINE<br/>"
        f"I&amp;I APARTMENTS KRAGUJEVAC<br/>"
        f"RACUN BR. {rb}/{godina}</b></font>",
        ParagraphStyle("pec", parent=styles["Normal"], fontName="Helvetica-Bold",
                       fontSize=7.5, textColor=PINK)
    ))

    doc.build(elements)

# ─── MAIL SLANJE ─────────────────────────────────────────────────────────────
def posalji_mail(to_email: str, br_fakture: int, godina: int, pdf_path: str):
    msg = MIMEMultipart()
    msg["From"]    = GMAIL_USER
    msg["To"]      = to_email
    msg["Subject"] = f"Faktura br. {br_fakture}/{godina} - I&I Apartments"

    body = (
        f"Poštovani,\n\n"
        f"U prilogu se nalazi faktura br. {br_fakture}/{godina}.\n\n"
        f"Srdačan pozdrav,\n"
        f"Ivan Svetić\n"
        f"I&I Apartments Kragujevac"
    )
    msg.attach(MIMEText(body, "plain"))

    with open(pdf_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="Faktura_{br_fakture}_{godina}.pdf"')
    msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, to_email, msg.as_string())

# ─── TELEGRAM KOMANDE ────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tekst = (
        "👋 *I\\&I Apartments \\- Bot za Fakture*\n\n"
        "Komanda:\n"
        "`/faktura NazivKlijenta DatumOd DatumDo BrojNoci CenaPoNoci mail`\n\n"
        "*Primjer:*\n"
        "`/faktura YanfengInternational 29.05.2026 12.06.2026 14 30 mail@firma.com`\n\n"
        "Za naziv klijenta sa razmakom koristi underscore: `Yanfeng\\_International`\n"
        "Bot će automatski numerisati fakturu i poslati PDF na mail\\."
    )
    await update.message.reply_text(tekst, parse_mode="MarkdownV2")

async def faktura_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if len(args) != 6:
        await update.message.reply_text(
            "❌ Pogrešan format!\n\n"
            "Koristiti:\n"
            "/faktura NazivKlijenta DatumOd DatumDo BrojNoci CenaPoNoci mail\n\n"
            "Primjer:\n"
            "/faktura YanfengInternational 29.05.2026 12.06.2026 14 30 mail@firma.com"
        )
        return

    klijent_naziv = args[0].replace("_", " ")
    datum_od      = args[1]
    datum_do      = args[2]
    to_email      = args[5]

    try:
        broj_noci     = int(args[3])
        cena_po_noci  = float(args[4])
    except ValueError:
        await update.message.reply_text("❌ Broj noći i cijena moraju biti brojevi!")
        return

    await update.message.reply_text("⏳ Generišem fakturu...")

    try:
        br_fakture, godina = get_next_broj()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            pdf_path = tmp.name

        napravi_pdf(
            br_fakture=br_fakture,
            godina=godina,
            klijent_naziv=klijent_naziv,
            datum_od=datum_od,
            datum_do=datum_do,
            broj_noci=broj_noci,
            cena_po_noci=cena_po_noci,
            output_path=pdf_path,
        )

        posalji_mail(to_email, br_fakture, godina, pdf_path)

        ukupno = broj_noci * cena_po_noci
        await update.message.reply_document(
            document=open(pdf_path, "rb"),
            filename=f"Faktura_{br_fakture}_{godina}.pdf",
            caption=(
                f"✅ *Faktura {br_fakture}/{godina}* napravljena i poslata!\n\n"
                f"👤 Klijent: {klijent_naziv}\n"
                f"📅 {datum_od} → {datum_do} ({broj_noci} noći)\n"
                f"💶 {cena_po_noci:.0f}€/noć = *{ukupno:.0f}€ / {ukupno*KURS:,.0f} din*\n"
                f"📧 Poslato na: {to_email}"
            ),
            parse_mode="Markdown"
        )
        os.unlink(pdf_path)

    except Exception as e:
        log.exception("Greška pri generisanju fakture")
        await update.message.reply_text(f"❌ Greška: {e}")

async def status_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    br, god = peek_broj()
    await update.message.reply_text(f"📊 Sljedeća faktura će biti: *{br}/{god}*", parse_mode="Markdown")

# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("faktura", faktura_cmd))
    app.add_handler(CommandHandler("status",  status_cmd))
    log.info("Bot pokrenut...")
    app.run_polling()

if __name__ == "__main__":
    main()
