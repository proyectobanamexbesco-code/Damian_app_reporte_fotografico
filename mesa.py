import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime
from PIL import Image
import os
import smtplib
from email.message import EmailMessage
import io
import time
import uuid
from pypdf import PdfWriter

# --- RUTAS PARA LA NUBE (LOGOTIPO) ---
LOGO_PATH = "logo.jpg"

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="BESCO | App Damian", layout="wide")

st.markdown("""
    <style>
    .stApp { color: #262730 !important; }
    .stButton > button { color: white !important; background-color: #E21836 !important; }
    h1, h2, h3 { color: #1E3A5F !important; }
    div[data-testid="stExpander"] div[role="button"] p { font-weight: bold !important; color: #1E3A5F !important; }
    </style>
    """, unsafe_allow_html=True)

class BESCO_PDF(FPDF):
    def __init__(self):
        super().__init__()
        self.section_count = 1

    def header(self):
        # BLINDAJE: Try/Except para que el PDF no explote si el logo tiene un formato extraño
        if os.path.exists(LOGO_PATH):
            try:
                self.image(LOGO_PATH, x=10, y=8, h=25)
            except Exception:
                pass # Si el logo falla, lo ignora y continúa creando el PDF
                
        self.set_font('Arial', 'B', 12)
        self.set_text_color(30, 58, 95)
        self.set_xy(100, 15)
        self.cell(0, 10, 'REPORTE DE SERVICIO TÉCNICO - APP DAMIAN', 0, 1, 'R')
        self.set_font('Arial', '', 9)
        self.set_x(100)
        self.cell(0, 5, f"Emisión del Reporte: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 1, 'R')
        self.ln(12)

    def add_custom_section(self, title):
        self.set_fill_color(30, 58, 95)
        self.set_font('Arial', 'B', 11)
        self.set_text_color(255, 255, 255)
        self.cell(0, 8, f"{self.section_count}. {title.upper()}", 0, 1, 'L', fill=True)
        self.section_count += 1
        self.ln(2)
        self.set_text_color(0, 0, 0)

    def photo_grid(self, title, photos, eq_index=0, prefix="img"):
        if not photos: return
        self.add_custom_section(title)
        ancho_foto, alto_foto, espacio_v, margen_inf = 90, 65, 75, 280
        
        for i, foto in enumerate(photos):
            foto.seek(0)
            img = Image.open(foto).convert("RGB")
            temp_p = f"temp_{prefix}_{uuid.uuid4().hex}.jpg"
            # BLINDAJE: Forzamos que se guarde estrictamente como JPEG
            img.save(temp_p, format="JPEG")
            
            col = i % 2
            if col == 0 and self.get_y() + espacio_v > margen_inf:
                self.add_page()
                self.set_font('Arial', 'I', 9); self.set_text_color(100, 100, 100)
                self.cell(0, 6, f"(Continuación) {title}", 0, 1, 'L')
                self.set_text_color(0, 0, 0); self.ln(2)
                
            y_act = self.get_y()
            self.image(temp_p, x=10 + (col * 95), y=y_act, w=ancho_foto, h=alto_foto)
            if col == 1 or i == len(photos) - 1: self.set_y(y_act + espacio_v)
        self.ln(5)

    def folio_grid(self, title, photo_files):
        if not photo_files: return
        for i, foto in enumerate(photo_files[:4]):
            self.add_page()
            self.add_custom_section(f"{title} - Evidencia {i+1}")
            foto.seek(0)
            img = Image.open(foto).convert("RGB")
            temp_folio = f"temp_folio_{uuid.uuid4().hex}.jpg"
            img.save(temp_folio, format="JPEG")
            
            avail_w, avail_h = 190, 240
            img_w, img_h = img.size
            escala = min(avail_w/img_w, avail_h/img_h)
            final_w, final_h = img_w * escala, img_h * escala
            self.image(temp_folio, x=10 + (190 - final_w) / 2, y=self.get_y() + 5, w=final_w, h=final_h)

def enviar_correo(pdf_bytes, cliente, folio, sucursal, oficina, nombre_archivo, correos_extra, fecha_ejec, lista_destinatarios):
    try:
        remitente = st.secrets["EMAIL_SENDER"]
        password = st.secrets["EMAIL_PASSWORD"]
        destinatarios = list(set(lista_destinatarios + ([c.strip() for c in correos_extra.split(",")] if correos_extra else [])))

        msg = EmailMessage()
        msg['Subject'] = f"Reporte Fotográfico BESCO (Damian): {cliente} | TK: {folio} | Of: {oficina}"
        msg['From'] = remitente
        msg['To'] = ", ".join(destinatarios) 
        msg.set_content(f"Se ha generado un nuevo reporte múltiple desde la App Damian.\n\nFecha Ejecución: {fecha_ejec}\nOficina: {oficina}\nCliente: {cliente}\nFolio: {folio}\nSucursal: {sucursal}")
        msg.add_attachment(pdf_bytes, maintype='application', subtype='pdf', filename=nombre_archivo)

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(remitente, password)
            smtp.send_message(msg)
        return True
    except Exception as e:
        # Se muestra un error visible si falla la conexión del correo
        st.error("❌ Ocurrió un problema al enviar el correo. Revise la configuración de sus contraseñas (Secrets).")
        print(e)
        return False

# --- INTERFAZ ---
st.title("📑 Sistema de Evidencia Técnica BESCO - App Damian")

st.subheader("1. Identificación General del Servicio")
c_g1, c_g2, c_g3, c_g4 = st.columns([2, 1, 1, 1.5])
cliente = c_g1.text_input("Cliente")
folio = c_g2.text_input("Folio / OT / TK")
estado_op = c_g3.selectbox("Estado Global", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], index=4)
fecha_ejecucion = c_g4.date_input("Fecha de Ejecución", datetime.now())

col_loc1, col_loc2 = st.columns(2)
sucursal = col_loc1.text_input("Sucursal / Inmueble")
oficina = col_loc2.selectbox("Oficina Responsable", ["Acapulco", "Toluca", "Pachuca", "Michoacán", "Zonas/ CDMX", "CDMX", "Ben & Company", "BX+", "Emerson", "Odoo"])

c_t1, c_t2, c_t3, c_t4 = st.columns(4)
tecnico = c_t1.text_input("Técnico Asignado")
supervisor = c_t2.text_input("Supervisor")
tipo_serv = c_t3.selectbox("Servicio", ["Preventivo", "Correctivo", "Emergencia"])
referencia = c_t4.selectbox("Referencia", ["Con Ticket", "Sin Ticket"])

st.markdown("---")

st.subheader("2. Evidencia Documental (Reporte Físico)")
st.info("📌 Puede subir hasta 4 fotos (JPG/PNG) y/o archivos PDF del reporte firmado.")
archivos_folio = st.file_uploader("Subir Folio BESCO", type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True)

st.markdown("---")

st.subheader("3. Equipos a Reportar")
num_equipos = st.number_input("¿Cuántos equipos se atendieron?", min_value=1, max_value=20, value=1)

equipos_data = []
for i in range(num_equipos):
    with st.expander(f"CONFIGURACIÓN EQUIPO {i+1}", expanded=True):
        esp = st.selectbox("Categoría", ["Ninguna", "Aire Acondicionado", "Tableros Eléctricos", "Hidroneumático", "Otros"], key=f"esp_{i}")
        meds, otros = {}, ""
        
        if esp == "Aire Acondicionado":
            cols = st.columns(4)
            meds['Succión'] = cols[0].text_input("Succión", key=f"s_{i}")
            meds['Descarga'] = cols[1].text_input("Descarga", key=f"d_{i}")
            meds['Salida'] = cols[2].text_input("Salida", key=f"t_{
