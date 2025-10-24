# app.py
"""
Good Luck Board - Premium Redesign with Google Sheets
A beautifully designed exam wishes board with modern UI/UX and cloud storage
"""

import os
import json
import uuid
from pathlib import Path
from io import BytesIO
from datetime import datetime
from textwrap import wrap
import logging

import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
import base64

# Google Sheets integration
try:
    import gspread
    from google.oauth2.service_account import Credentials
    from google.auth.exceptions import GoogleAuthError
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False

# ---------- CONFIG & THEME ----------
DATA_FILE = Path("messages.json")
APP_TITLE = "🎓 Good Luck Board"
APP_SUBTITLE = "Send warm exam wishes! ✨"
ADMIN_SECRET_KEY_NAME = "ADMIN_KEY"

# Google Sheets configuration
GOOGLE_SHEET_NAME = "ExamWishes"

# Modern color palette
COLORS = {
    "primary": "#6366F1",
    "primary_dark": "#4F46E5",
    "secondary": "#EC4899",
    "accent": "#10B981",
    "background": "#F8FAFC",
    "card_bg": "#FFFFFF",
    "text_primary": "#1E293B",
    "text_secondary": "#64748B",
    "border": "#E2E8F0",
    "success": "#10B981",
    "warning": "#F59E0B"
}

DEFAULT_TEMPLATES = [
    {"label": "Short & Encouraging", "text": "You've got this! 💪 Keep calm and trust your preparation.", "icon": "💪"},
    {"label": "Inspirational", "text": "Believe in yourself — your hard work will pay off! 🌟📚", "icon": "🌟"},
    {"label": "Light & Funny", "text": "Go smash those exams like a boss! 🧠⚡ (Don't forget to breathe.)", "icon": "😄"},
    {"label": "Supportive & Warm", "text": "Wishing you clarity, focus and success. All the best! ❤️✍️", "icon": "❤️"},
    {"label": "Calm & Focused", "text": "One question at a time. You've prepared well — now show what you know. 🌿", "icon": "🌿"}
]

EMOJI_CATEGORIES = {
    "🌟 Popular": ["🎉", "🎯", "💪", "🌟", "✨", "🔥", "💯", "🥳", "🎓", "📚"],
    "📚 Academic": ["📖", "📝", "✏️", "📌", "🔔", "🧠", "💡", "⭐", "🏆", "✅"],
    "💝 Support": ["❤️", "🤍", "💙", "🙌", "👏", "🤞", "🍀", "☘️", "🌈", "🌿"],
    "😊 Emotions": ["😊", "😄", "🤩", "🥰", "😎", "🤗", "🎊", "🎈", "💫", "⚡"]
}

# ---------- STORAGE UTILITIES ----------
def init_google_sheets():
    """Initialize Google Sheets connection using Streamlit secrets"""
    if not GOOGLE_SHEETS_AVAILABLE:
        return None
    
    try:
        # Check if secrets are configured
        if 'GOOGLE_CREDENTIALS' not in st.secrets:
            return None
        
        # Get credentials from secrets
        credentials_dict = dict(st.secrets['GOOGLE_CREDENTIALS'])
        
        # Validate required fields
        required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        missing_fields = [field for field in required_fields if field not in credentials_dict or not credentials_dict[field]]
        
        if missing_fields:
            return None
        
        # Use the correct scope for Google Sheets API
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        try:
            creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
            client = gspread.authorize(creds)
        except (GoogleAuthError, Exception):
            return None
        
        # Try to open existing sheet or create new one
        try:
            sheet = client.open(GOOGLE_SHEET_NAME)
        except gspread.SpreadsheetNotFound:
            try:
                # Try to create the sheet if it doesn't exist
                sheet = client.create(GOOGLE_SHEET_NAME)
                # Make it accessible to anyone with the link (optional)
                sheet.share(None, perm_type='anyone', role='writer')
            except Exception:
                return None
        except Exception:
            return None
        
        # Get the first worksheet
        worksheet = sheet.sheet1
        
        # Set up headers if empty
        try:
            if not worksheet.get_all_values():
                worksheet.append_row(["ID", "Name", "Recipient", "Message", "Tone", "Timestamp"])
        except Exception:
            return None
        
        return worksheet
        
    except Exception:
        return None

def read_messages():
    """Read messages from Google Sheets or fall back to local JSON"""
    # Try Google Sheets first
    worksheet = st.session_state.get('google_worksheet')
    if worksheet:
        try:
            records = worksheet.get_all_records()
            messages = []
            for record in records:
                # Skip empty rows or header rows
                if record.get("ID") and record.get("ID") != "ID" and record.get("ID").strip():
                    messages.append({
                        "id": record.get("ID", ""),
                        "name": record.get("Name", "Anonymous"),
                        "recipient": record.get("Recipient", "Anyone"),
                        "message": record.get("Message", ""),
                        "tone": record.get("Tone", ""),
                        "timestamp": record.get("Timestamp", "")
                    })
            return messages
        except Exception:
            pass
    
    # Fall back to local JSON
    if not DATA_FILE.exists():
        return []
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def write_messages(messages):
    """Write messages to Google Sheets or fall back to local JSON"""
    # Try Google Sheets first
    worksheet = st.session_state.get('google_worksheet')
    if worksheet:
        try:
            # Clear existing data (keep headers)
            worksheet.clear()
            worksheet.append_row(["ID", "Name", "Recipient", "Message", "Tone", "Timestamp"])
            
            # Add all messages
            for msg in messages:
                worksheet.append_row([
                    msg.get("id", ""),
                    msg.get("name", "Anonymous"),
                    msg.get("recipient", "Anyone"),
                    msg.get("message", ""),
                    msg.get("tone", ""),
                    msg.get("timestamp", "")
                ])
            return
        except Exception:
            pass
    
    # Fall back to local JSON
    try:
        with DATA_FILE.open("w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def append_message(entry):
    """Append a single message to storage"""
    msgs = read_messages()
    msgs.append(entry)
    write_messages(msgs)

def delete_message_by_id(msg_id):
    """Delete a message by ID"""
    msgs = read_messages()
    msgs = [m for m in msgs if m.get("id") != msg_id]
    write_messages(msgs)

def get_admin_secret():
    return st.secrets.get(ADMIN_SECRET_KEY_NAME) if ADMIN_SECRET_KEY_NAME in st.secrets else None

def is_admin_key_valid(provided_key):
    secret = get_admin_secret()
    if not secret:
        return False
    return provided_key and provided_key == secret

# ---------- PDF GENERATION ----------
def generate_pdf_buffer(messages, title="Good Luck Board Messages"):
    """Create a beautiful PDF with modern styling"""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='MessageStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.darkblue,
        spaceAfter=12,
    ))
    
    elements = []
    
    # Title
    title_style = ParagraphStyle(
        name='TitleStyle',
        parent=styles['Heading1'],
        textColor=colors.HexColor(COLORS["primary"]),
        spaceAfter=30,
        alignment=1
    )
    elements.append(Paragraph(title, title_style))
    
    for msg in reversed(messages):
        # Header with gradient-like styling using table
        header_data = [
            [
                Paragraph(f"<b>From:</b> {msg.get('name','Anonymous')}", styles['Heading3']),
                Paragraph(f"<b>To:</b> {msg.get('recipient','Anyone')}", styles['Heading3']),
                Paragraph(f"<b>Style:</b> {msg.get('tone','')}", styles['Heading3'])
            ]
        ]
        
        header_table = Table(header_data, colWidths=[doc.width/3]*3)
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(COLORS["background"])),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor(COLORS["text_primary"])),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(header_table)
        
        # Timestamp
        timestamp_style = ParagraphStyle(
            name='TimestampStyle',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.gray,
            alignment=2
        )
        elements.append(Paragraph(msg.get("timestamp", ""), timestamp_style))
        elements.append(Spacer(1, 8))
        
        # Message body
        message_text = msg.get("message", "").replace("\n", "<br/>")
        elements.append(Paragraph(message_text, styles['MessageStyle']))
        elements.append(Spacer(1, 20))
        
        # Divider
        elements.append(Spacer(1, 1))
        elements.append(Table([[None]], colWidths=[doc.width], style=[
            ('LINEABOVE', (0, 0), (-1, -1), 1, colors.HexColor(COLORS["border"]))
        ]))
        elements.append(Spacer(1, 20))
    
    doc.build(elements)
    buf.seek(0)
    return buf

# ---------- UI UTILITIES ----------
def apply_custom_styles():
    """Apply custom CSS for modern styling"""
    st.markdown(f"""
    <style>
    /* Main background */
    .stApp {{
        background: linear-gradient(135deg, {COLORS['background']} 0%, #FFFFFF 100%);
    }}
    
    /* Headers */
    h1, h2, h3 {{
        color: {COLORS['text_primary']} !important;
        font-weight: 700 !important;
    }}
    
    /* Cards */
    .message-card {{
        background: {COLORS['card_bg']};
        border-radius: 16px;
        padding: 24px;
        margin: 16px 0;
        border: 1px solid {COLORS['border']};
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}
    
    .message-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0,0,0,0.12);
    }}
    
    /* Buttons */
    .stButton>button {{
        border-radius: 12px;
        padding: 12px 24px;
        font-weight: 600;
        border: none;
        background: linear-gradient(135deg, {COLORS['primary']}, {COLORS['primary_dark']});
        color: white;
        transition: all 0.3s ease;
    }}
    
    .stButton>button:hover {{
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4);
    }}
    
    /* Sidebar - Increased width */
    section[data-testid="stSidebar"] {{
        width: 380px !important;
        min-width: 380px !important;
    }}
    
    .css-1d391kg {{
        background: {COLORS['card_bg']};
        border-right: 1px solid {COLORS['border']};
        padding: 2rem 1.5rem;
    }}
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
    }}
    
    .stTabs [data-baseweb="tab"] {{
        background: {COLORS['background']};
        border-radius: 12px 12px 0 0;
        padding: 16px 24px;
        border: 1px solid {COLORS['border']};
        font-weight: 600;
    }}
    
    .stTabs [aria-selected="true"] {{
        background: {COLORS['primary']} !important;
        color: white !important;
    }}
    
    /* Form inputs */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {{
        border-radius: 12px;
        border: 2px solid {COLORS['border']};
        padding: 12px;
    }}
    
    .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {{
        border-color: {COLORS['primary']};
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
    }}
    
    /* Select boxes */
    .stSelectbox>div>div {{
        border-radius: 12px;
        border: 2px solid {COLORS['border']};
    }}
    
    /* Success messages */
    .stAlert {{
        border-radius: 12px;
    }}
    
    /* Custom badge for tones */
    .tone-badge {{
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8em;
        font-weight: 600;
        margin-left: 8px;
    }}
    
    /* Emoji buttons */
    .emoji-btn {{
        font-size: 1.5em;
        padding: 8px;
        border: 2px solid transparent;
        border-radius: 8px;
        background: {COLORS['background']};
        cursor: pointer;
        transition: all 0.2s ease;
    }}
    
    .emoji-btn:hover {{
        border-color: {COLORS['primary']};
        background: white;
        transform: scale(1.1);
    }}
    
    /* Template buttons */
    .template-btn {{
        width: 100%;
        margin: 4px 0;
        border-radius: 10px;
        border: 1px solid {COLORS['border']};
        padding: 12px;
        background: {COLORS['background']};
        transition: all 0.2s ease;
    }}
    
    .template-btn:hover {{
        border-color: {COLORS['primary']};
        background: white;
        transform: translateY(-1px);
    }}
    
    /* Horizontal category buttons */
    .category-row {{
        display: flex;
        gap: 4px;
        margin-bottom: 10px;
    }}
    
    .category-btn {{
        flex: 1;
        font-size: 0.8em !important;
        padding: 6px 8px !important;
    }}
    </style>
    """, unsafe_allow_html=True)

def create_tone_badge(tone):
    """Create a styled badge for message tones"""
    tone_colors = {
        "inspirational": COLORS["primary"],
        "encouraging": COLORS["success"],
        "funny": COLORS["warning"],
        "calm": COLORS["secondary"],
        "formal": COLORS["text_secondary"],
        "custom": "#6B7280"
    }
    color = tone_colors.get(tone, COLORS["text_secondary"])
    return f'<span class="tone-badge" style="background: {color}15; color: {color}; border: 1px solid {color}30;">{tone}</span>'

# ---------- STREAMLIT UI ----------
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_custom_styles()

# Initialize Google Sheets connection
if 'google_worksheet' not in st.session_state:
    st.session_state.google_worksheet = init_google_sheets()

# Initialize session state
if "emoji_buffer" not in st.session_state:
    st.session_state.emoji_buffer = []
if "form" not in st.session_state:
    st.session_state.form = {"name": "", "message": "", "tone": "inspirational"}
if "active_emoji_category" not in st.session_state:
    st.session_state.active_emoji_category = "🌟 Popular"
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

# Header with modern design and featured recipients
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown(f"""
    <div style="text-align: center; padding: 1rem 0;">
        <h1 style="font-size: 3rem; margin-bottom: 0.5rem; background: linear-gradient(135deg, {COLORS['primary']}, {COLORS['secondary']}); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{APP_TITLE}</h1>
        <p style="font-size: 1.2rem; color: {COLORS['text_secondary']}; margin-top: 0;">{APP_SUBTITLE}</p>
    </div>
    """, unsafe_allow_html=True)

# Featured recipients section
st.markdown(f"""
<div style="text-align: center; background: {COLORS['primary']}10; padding: 1.5rem; border-radius: 16px; margin: 1rem 0; border: 2px solid {COLORS['primary']}20;">
    <h3 style="color: {COLORS['primary']}; margin-bottom: 1rem;">🎯 Wishing Best of Luck To:</h3>
    <div style="display: flex; justify-content: center; gap: 3rem; font-size: 1.3rem; font-weight: bold;">
        <div style="color: {COLORS['primary']};">🎓 Chelsea</div>
        <div style="color: {COLORS['secondary']};">📚 Nagel</div>
    </div>
    <p style="color: {COLORS['text_secondary']}; margin-top: 1rem; font-size: 1rem;">
        Send your warm wishes and encouragement to help them succeed in their exams!
    </p>
</div>
""", unsafe_allow_html=True)

# Simple status indicator for regular users
storage_connected = st.session_state.google_worksheet is not None
status_color = COLORS["success"] if storage_connected else COLORS["warning"]
status_icon = "✅" if storage_connected else "🔄"
status_text = "Storage Connected" if storage_connected else "Processing..."

st.sidebar.markdown(f"""
<div style="background: {status_color}15; padding: 8px 12px; border-radius: 8px; border: 1px solid {status_color}30; margin-bottom: 1rem;">
    <small style="color: {status_color}; font-weight: 600;">{status_icon} {status_text}</small>
</div>
""", unsafe_allow_html=True)

# Enhanced Sidebar with professional layout
with st.sidebar:
    st.markdown(f"""
    <div style="padding: 1rem 0; text-align: center;">
        <h2 style="color: {COLORS['text_primary']}; margin-bottom: 0;">✨ Quick Tools</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Templates section
    with st.expander("🎨 Message Templates", expanded=True):
        st.markdown("**Choose a template to get started:**")
        for template in DEFAULT_TEMPLATES:
            if st.button(
                f"{template['icon']} {template['label']}", 
                key=f"tmpl_{template['label']}", 
                use_container_width=True
            ):
                st.session_state.form["message"] = template["text"]
                st.rerun()
    
    st.markdown("---")
    
    # Enhanced emoji picker with horizontal categories
    with st.expander("😊 Emoji Picker", expanded=True):
        # Horizontal category tabs with smaller font
        categories = list(EMOJI_CATEGORIES.keys())
        st.markdown("**Categories:**")
        
        # Create horizontal layout for categories
        cat_cols = st.columns(len(categories))
        for i, category in enumerate(categories):
            is_active = st.session_state.active_emoji_category == category
            if cat_cols[i].button(
                category, 
                key=f"cat_{i}", 
                use_container_width=True,
                type="primary" if is_active else "secondary"
            ):
                st.session_state.active_emoji_category = category
                st.rerun()
        
        st.markdown("---")
        
        # Emoji grid with better spacing
        emojis = EMOJI_CATEGORIES[st.session_state.active_emoji_category]
        st.markdown(f"**{st.session_state.active_emoji_category}**")
        cols = st.columns(5)
        for i, emj in enumerate(emojis):
            col = cols[i % 5]
            if col.button(emj, key=f"emoji_{i}_{emj}", use_container_width=True):
                st.session_state.emoji_buffer.append(emj)
                st.rerun()
        
        # Selected emojis with better display
        if st.session_state.emoji_buffer:
            st.markdown("---")
            st.markdown("**Your selected emojis:**")
            selected_text = " ".join(st.session_state.emoji_buffer)
            st.markdown(f'''
            <div style="
                padding: 12px; 
                background: {COLORS["background"]}; 
                border-radius: 8px; 
                text-align: center; 
                font-size: 1.2em;
                border: 1px solid {COLORS["border"]};
                margin: 8px 0;
            ">{selected_text}</div>
            ''', unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            if col1.button("Add to Message", use_container_width=True):
                if "message" in st.session_state.form:
                    st.session_state.form["message"] += " " + " ".join(st.session_state.emoji_buffer)
                st.session_state.emoji_buffer = []
                st.rerun()
            if col2.button("Clear Emojis", use_container_width=True):
                st.session_state.emoji_buffer = []
                st.rerun()
    
    st.markdown("---")
    
    # Enhanced Admin section
    with st.expander("🔐 Admin Access", expanded=False):
        if not st.session_state.admin_authenticated:
            st.markdown("**Administrative Controls**")
            st.markdown("Enter admin password to access management features.")
            admin_input = st.text_input("Admin Password", type="password", key="admin_input")
            
            if st.button("Authenticate", use_container_width=True):
                if admin_input and is_admin_key_valid(admin_input):
                    st.session_state.admin_authenticated = True
                    st.success("✅ Admin Authenticated")
                    st.rerun()
                else:
                    st.error("❌ Invalid admin password")
        else:
            st.success("✅ Admin Authenticated")
            
            # Storage details for admin
            storage_type = "Google Sheets" if st.session_state.google_worksheet else "Local JSON"
            storage_status = "Connected" if st.session_state.google_worksheet else "Local Storage"
            storage_color = COLORS["success"] if st.session_state.google_worksheet else COLORS["warning"]
            
            st.markdown(f"""
            <div style="background: {COLORS['background']}; padding: 1rem; border-radius: 8px; border: 1px solid {COLORS['border']}; margin-bottom: 1rem;">
                <h4 style="margin: 0 0 0.5rem 0; color: {COLORS['text_primary']};">💾 Storage Details</h4>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-size: 0.8rem; color: {COLORS['text_secondary']};">Type</div>
                        <div style="font-size: 1rem; font-weight: bold; color: {storage_color};">{storage_type}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.8rem; color: {COLORS['text_secondary']};">Status</div>
                        <div style="font-size: 1rem; font-weight: bold; color: {storage_color};">{storage_status}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Admin statistics
            messages = read_messages()
            total_messages = len(messages)
            unique_senders = len({m.get('name', 'Anonymous') for m in messages})
            
            st.markdown(f"""
            <div style="background: {COLORS['background']}; padding: 1rem; border-radius: 8px; border: 1px solid {COLORS['border']}; margin-bottom: 1rem;">
                <h4 style="margin: 0 0 0.5rem 0; color: {COLORS['text_primary']};">📊 Statistics</h4>
                <div style="display: flex; justify-content: space-between;">
                    <div>
                        <div style="font-size: 0.8rem; color: {COLORS['text_secondary']};">Total Messages</div>
                        <div style="font-size: 1.2rem; font-weight: bold; color: {COLORS['primary']};">{total_messages}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.8rem; color: {COLORS['text_secondary']};">Unique Senders</div>
                        <div style="font-size: 1.2rem; font-weight: bold; color: {COLORS['secondary']};">{unique_senders}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Export section for admin only
            if messages:
                st.markdown("### 📤 Export Messages")
                col1, col2 = st.columns(2)
                
                with col1:
                    # JSON export
                    json_bytes = json.dumps(messages, ensure_ascii=False, indent=2).encode("utf-8")
                    st.download_button(
                        "📊 Download JSON",
                        data=json_bytes,
                        file_name="good_luck_messages.json",
                        mime="application/json",
                        use_container_width=True
                    )
                
                with col2:
                    # PDF export
                    pdf_buf = generate_pdf_buffer(messages)
                    st.download_button(
                        "📄 Download PDF Report",
                        data=pdf_buf,
                        file_name="good_luck_messages.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
            
            # Admin actions
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Clear All", use_container_width=True):
                    write_messages([])
                    st.success("All messages cleared!")
                    st.rerun()
            
            with col2:
                if st.button("🔄 Refresh", use_container_width=True):
                    st.rerun()
            
            if st.button("🚪 Logout Admin", use_container_width=True):
                st.session_state.admin_authenticated = False
                st.rerun()
            
            # Message management
            if messages:
                st.markdown("**Message Management:**")
                for msg in messages[-5:]:  # Show last 5 messages
                    with st.container():
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"""
                            <div style="
                                padding: 8px 12px; 
                                background: {COLORS['background']}; 
                                border-radius: 8px; 
                                border: 1px solid {COLORS['border']};
                                margin: 4px 0;
                                font-size: 0.8em;
                            ">
                                <strong>{msg['name']}</strong><br/>
                                <span style="color: {COLORS['text_secondary']};">{msg['message'][:50]}...</span>
                            </div>
                            """, unsafe_allow_html=True)
                        with col2:
                            if st.button("🗑️", key=f"del_{msg['id']}", use_container_width=True):
                                delete_message_by_id(msg['id'])
                                st.success("Message deleted!")
                                st.rerun()

# Main content area
tab_send, tab_view = st.tabs(["✍️ Compose Message", "📜 View Messages"])

# Send Message Tab
with tab_send:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(f"""
        <div style="background: {COLORS['card_bg']}; padding: 2rem; border-radius: 16px; border: 1px solid {COLORS['border']};">
            <h2 style="color: {COLORS['text_primary']}; margin-bottom: 1.5rem;">✨ Create Your Message</h2>
        """, unsafe_allow_html=True)
        
        with st.form("compose_form", clear_on_submit=True):
            # Name input
            name = st.text_input(
                "**Your Name** ✏️",
                placeholder="Enter your name (or stay anonymous)",
                value=st.session_state.form["name"],
                max_chars=50
            )
            
            # Tone selection
            tone = st.selectbox(
                "**Message Tone** 🎭",
                ["inspirational", "encouraging", "funny", "calm", "formal", "custom"],
                index=["inspirational", "encouraging", "funny", "calm", "formal", "custom"].index(st.session_state.form.get("tone", "inspirational"))
            )
            
            # Message area
            message = st.text_area(
                "**Your Message** 💫",
                height=200,
                placeholder="Write your encouraging message here... (Markdown supported)",
                value=st.session_state.form.get("message", "")
            )
            
            # Submit button
            submitted = st.form_submit_button(
                "🚀 Send Your Wish",
                use_container_width=True
            )
            
            if submitted:
                if not message.strip():
                    st.error("Please write a message before sending!")
                else:
                    final_message = message.strip()
                    
                    # Add emojis to the end of the message
                    if st.session_state.emoji_buffer:
                        final_message = final_message + " " + " ".join(st.session_state.emoji_buffer)
                    
                    entry = {
                        "id": str(uuid.uuid4()),
                        "name": (name.strip() or "Anonymous"),
                        "recipient": "Chelsea & Nagel",  # Fixed recipient
                        "message": final_message,
                        "tone": tone,
                        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                    }
                    
                    append_message(entry)
                    st.session_state.emoji_buffer = []
                    st.session_state.form = {"name": "", "message": "", "tone": "inspirational"}
                    st.success("🎉 Your message was sent successfully!")
                    st.balloons()

# View Messages Tab
with tab_view:
    messages = read_messages()
    
    if not messages:
        st.markdown(f"""
        <div style="text-align: center; padding: 4rem 2rem; background: {COLORS['card_bg']}; border-radius: 16px; border: 1px solid {COLORS['border']};">
            <h3 style="color: {COLORS['text_secondary']}; margin-bottom: 1rem;">📝 No Messages Yet</h3>
            <p style="color: {COLORS['text_secondary']}; font-size: 1.1rem;">Be the first to send some encouragement! 💫</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Filters
        col1, col2 = st.columns(2)
        with col1:
            senders = sorted({m.get("name", "Anonymous") for m in messages})
            sender_filter = st.selectbox("Filter by sender", ["All"] + senders)
        
        # Apply filters
        filtered = messages
        if sender_filter != "All":
            filtered = [m for m in filtered if m.get("name") == sender_filter]
        
        # Statistics
        st.markdown(f"""
        <div style="background: {COLORS['card_bg']}; padding: 1rem; border-radius: 12px; margin: 1rem 0; border: 1px solid {COLORS['border']};">
            <div style="display: flex; justify-content: space-around; text-align: center;">
                <div>
                    <div style="font-size: 0.9rem; color: {COLORS['text_secondary']};">Total Messages</div>
                    <div style="font-size: 1.5rem; font-weight: bold; color: {COLORS['primary']};">{len(filtered)}</div>
                </div>
                <div>
                    <div style="font-size: 0.9rem; color: {COLORS['text_secondary']};">Unique Senders</div>
                    <div style="font-size: 1.5rem; font-weight: bold; color: {COLORS['secondary']};">{len({m.get('name', 'Anonymous') for m in filtered})}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Message cards
        for m in reversed(filtered):
            name = m.get("name", "Anonymous")
            tone = m.get("tone", "")
            ts = m.get("timestamp", "")
            msg_body = m.get("message", "")
            
            # Create beautiful card
            st.markdown(f"""
            <div class="message-card">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">
                    <div>
                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                            <h4 style="margin: 0; color: {COLORS['text_primary']};">{name}</h4>
                            {create_tone_badge(tone)}
                        </div>
                    </div>
                    <div style="font-size: 0.8rem; color: {COLORS['text_secondary']};">{ts}</div>
                </div>
                <div style="
                    padding: 1.5rem;
                    background: {COLORS['background']};
                    border-radius: 12px;
                    border-left: 4px solid {COLORS['primary']};
                    font-size: 1rem;
                    line-height: 1.6;
                    color: {COLORS['text_primary']};
                    white-space: pre-wrap;
                ">
                    {msg_body}
                </div>
            </div>
            """, unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown(f"""
<div style="text-align: center; color: {COLORS['text_secondary']}; padding: 2rem 0;">
    <p>Made with ❤️ for spreading positivity during exams</p>
    <p style="font-size: 0.9rem;">📧 Messages: {len(read_messages())}</p>
</div>
""", unsafe_allow_html=True)