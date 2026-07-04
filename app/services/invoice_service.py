"""
PDF invoice generation using ReportLab.
Generates GST-compliant payment receipts for Indian gym operations.

Returns raw bytes — caller streams as HTTP response.
PDFs are generated on-demand (acceptable for single-gym scale).
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from io import BytesIO
from decimal import Decimal
from datetime import date, datetime
from typing import Optional
from app.core.config import settings

# Brand colors
ORANGE = colors.HexColor("#FF6B00")
DARK = colors.HexColor("#1a1a1a")
LIGHT_GREY = colors.HexColor("#f4f4f4")
SUCCESS_GREEN = colors.HexColor("#22C55E")

def generate_payment_receipt_pdf(
    receipt_number: str,
    member_name: str,
    member_email: str,
    member_id: str,
    plan_name: str,
    duration_days: int,
    membership_start: date,
    membership_end: date,
    amount_paid: Decimal,
    payment_method: str,
    transaction_reference: Optional[str],
    payment_date: datetime,
    collected_by_name: Optional[str] = None,
    discount_percent: float = 0.0,
) -> bytes:
    """
    Generates a GST-compliant A4 PDF receipt.
    Returns raw bytes to be streamed as HTTP response.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )

    # --- GST calculations ---
    subtotal = amount_paid
    discount_amount = subtotal * Decimal(str(discount_percent / 100))
    taxable = subtotal - discount_amount
    gst_amount = taxable * Decimal(str(settings.GYM_GST_PERCENT / 100))
    total = taxable + gst_amount

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=ORANGE,
        spaceAfter=15,
        alignment=TA_LEFT
    )
    
    header_style = ParagraphStyle(
        'GymName',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=colors.white,
        alignment=TA_CENTER
    )
    
    subheader_style = ParagraphStyle(
        'GymSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.white,
        alignment=TA_CENTER
    )

    normal_bold = ParagraphStyle(
        'NormalBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=DARK
    )

    right_bold = ParagraphStyle(
        'RightBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=DARK,
        alignment=TA_RIGHT
    )

    normal_text = ParagraphStyle(
        'NormalText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=DARK
    )

    right_text = ParagraphStyle(
        'RightText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=DARK,
        alignment=TA_RIGHT
    )

    badge_style = ParagraphStyle(
        'Badge',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=SUCCESS_GREEN,
        alignment=TA_CENTER
    )

    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        textColor=colors.HexColor("#777777"),
        alignment=TA_CENTER
    )

    story = []

    # 1. Header Banner
    banner_data = [
        [Paragraph("PRRO HEALTH CLUB", header_style)],
        [Paragraph(f"{settings.GYM_ADDRESS} | 📞 {settings.GYM_PHONE or 'N/A'} | ✉️ {settings.GYM_EMAIL}", subheader_style)]
    ]
    banner_table = Table(banner_data, colWidths=[170*mm])
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), ORANGE),
        ('PADDING', (0,0), (-1,-1), 12),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,1), (-1,1), 16),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 15))

    # 2. Receipt Label & Paid Badge
    receipt_header_data = [
        [
            Paragraph("PAYMENT RECEIPT", title_style),
            Paragraph("PAID ✓", badge_style)
        ]
    ]
    receipt_header_table = Table(receipt_header_data, colWidths=[110*mm, 60*mm])
    receipt_header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
    ]))
    story.append(receipt_header_table)
    story.append(HRFlowable(width="100%", thickness=1, color=ORANGE, spaceBefore=5, spaceAfter=15))

    # 4. Details Section (Member Details & Receipt Details)
    details_data = [
        [
            Paragraph("<b>MEMBER DETAILS</b>", normal_bold),
            Paragraph("<b>RECEIPT DETAILS</b>", normal_bold)
        ],
        [
            Paragraph(f"Name: {member_name}", normal_text),
            Paragraph(f"Receipt No: <b>{receipt_number}</b>", normal_text)
        ],
        [
            Paragraph(f"Email: {member_email}", normal_text),
            Paragraph(f"Date: {payment_date.strftime('%d %b %Y, %I:%M %p')}", normal_text)
        ],
        [
            Paragraph(f"Member ID: {member_id}", normal_text),
            Paragraph(f"Method: {payment_method.upper()}", normal_text)
        ]
    ]
    details_table = Table(details_data, colWidths=[85*mm, 85*mm])
    details_table.setStyle(TableStyle([
        ('PADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dddddd"), spaceBefore=5, spaceAfter=15))

    # 6. Membership details table
    membership_headers = [
        Paragraph("<b>Plan Name</b>", normal_bold),
        Paragraph("<b>Duration</b>", normal_bold),
        Paragraph("<b>Valid From</b>", normal_bold),
        Paragraph("<b>Valid Until</b>", normal_bold)
    ]
    membership_row = [
        Paragraph(plan_name, normal_text),
        Paragraph(f"{duration_days} days", normal_text),
        Paragraph(membership_start.strftime("%d %b %Y"), normal_text),
        Paragraph(membership_end.strftime("%d %b %Y"), normal_text)
    ]
    mem_table = Table([membership_headers, membership_row], colWidths=[60*mm, 35*mm, 37*mm, 38*mm])
    mem_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_GREY),
        ('PADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#dddddd")),
    ]))
    story.append(mem_table)
    story.append(Spacer(1, 20))

    # 8. Payment breakdown table
    breakdown_rows = []
    breakdown_rows.append([Paragraph("Subtotal", normal_text), Paragraph(f"₹{subtotal:,.2f}", right_text)])
    
    if discount_percent > 0:
        breakdown_rows.append([Paragraph(f"Discount ({discount_percent}%)", normal_text), Paragraph(f"-₹{discount_amount:,.2f}", right_text)])
        
    if settings.GYM_GST_PERCENT > 0:
        breakdown_rows.append([
            Paragraph(f"GST ({settings.GYM_GST_PERCENT}%){' - Reg: ' + settings.GYM_GST_NUMBER if settings.GYM_GST_NUMBER else ''}", normal_text),
            Paragraph(f"₹{gst_amount:,.2f}", right_text)
        ])
        
    breakdown_rows.append([Paragraph("<b>TOTAL PAID</b>", normal_bold), Paragraph(f"<b>₹{total:,.2f}</b>", right_bold)])
    
    breakdown_table = Table(breakdown_rows, colWidths=[110*mm, 60*mm])
    breakdown_table.setStyle(TableStyle([
        ('PADDING', (0,0), (-1,-1), 6),
        ('LINEBELOW', (0,-2), (1,-2), 1, colors.HexColor("#1a1a1a")),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#FFF3E0")),
        ('PADDING', (0,-1), (-1,-1), 8),
    ]))
    story.append(breakdown_table)
    story.append(Spacer(1, 15))

    # Transaction info
    tx_text = f"Payment Method: {payment_method.upper()}"
    if transaction_reference:
        tx_text += f" | Transaction Ref: {transaction_reference}"
    if collected_by_name:
        tx_text += f" | Collected By: {collected_by_name}"
    story.append(Paragraph(tx_text, normal_text))
    story.append(Spacer(1, 30))

    # 11. GST registration indicator if applicable
    if settings.GYM_GST_NUMBER:
        story.append(Paragraph(f"<font size=8 color='#555555'>GSTIN: {settings.GYM_GST_NUMBER}</font>", normal_text))
        story.append(Spacer(1, 10))

    # 12. Footer message
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dddddd"), spaceBefore=10, spaceAfter=15))
    story.append(Paragraph("Thank you for choosing Prro Health Club. Stay consistent, stay strong!", footer_style))

    doc.build(story)
    return buffer.getvalue()
