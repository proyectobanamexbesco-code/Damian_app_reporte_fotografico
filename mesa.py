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
        # --- BLINDAJE ABSOLUTO DEL LOGOTIPO ---
        # 1. Buscamos cualquier archivo que se parezca a tu logo
        logo_encontrado = None
        posibles_nombres = ["logo.jpg", "logo.jpeg", "logo.png", "Logo.jpg", "Logo.png", "logo"]
        for nombre in posibles_nombres:
            if os.path.exists(nombre):
                logo_encontrado = nombre
                break
        
        # 2. Si lo encuentra, lo purifica a JPEG estándar antes de imprimirlo
        if logo_encontrado:
            try:
                img_logo = Image.open(logo_encontrado).convert("RGB")
                temp_logo = "temp_logo_seguro.jpg"
                img_logo.save(temp_logo, format="JPEG")
                self.image(temp_logo, x=10, y=8, h=25)
            except Exception:
                pass # Si el archivo está corrupto, lo ignora para no colapsar la app
                
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
            meds['Salida'] = cols[2].text_input("Salida", key=f"t_{i}")
            meds['Amperaje'] = cols[3].text_input("Amp", key=f"a_{i}")
        elif esp == "Otros":
            otros = st.text_area("Detalles/Mediciones:", key=f"o_{i}")
            
        ca1, ca2, ca3 = st.columns(3)
        tag = ca1.text_input("TAG", key=f"tg_{i}")
        marca = ca2.text_input("Marca", key=f"mr_{i}")
        cap = ca3.text_input("Capacidad", key=f"cp_{i}")
        
        com = st.text_area("Comentarios", key=f"com_{i}")
        
        fa = st.file_uploader("Fotos ANTES", accept_multiple_files=True, key=f"fa_{i}")
        fd = st.file_uploader("Fotos DESPUÉS", accept_multiple_files=True, key=f"fd_{i}")
        
        equipos_data.append({"numero": i+1, "esp": esp, "meds": meds, "otros": otros, "tag": tag, "marca": marca, "cap": cap, "com": com, "fa": fa, "fd": fd})

st.subheader("4. Materiales Utilizados")
df_mat = st.data_editor(pd.DataFrame(columns=["Cantidad", "Descripción"]), num_rows="dynamic")

st.markdown("---")
st.subheader("5. Envío de Reporte")

mapeo_correos = {
    "Acapulco": ["itzallana.vazquez@besco.mx", "gerardo.fuentes@besco.mx"],
    "Toluca": ["policarpo.rosaliano@besco.mx", "monica.iniestra@besco.mx"],
    "Pachuca": ["german.constantino@besco.mx"],
    "Michoacán": ["cristobal.rodriguez@besco.mx", "ximena.acosta@besco.mx", "javier.zamano@besco.mx"],
    "Zonas/ CDMX": ["german.constantino@besco.mx", "andres.mayagoitia@besco.mx", "brenda.cervantes@besco.mx"],
    "CDMX": ["gerardo.mendez@besco.mx"],
    "Ben & Company": ["gerardo.mendez@besco.mx"], "BX+": ["gerardo.mendez@besco.mx"], "Emerson": ["gerardo.mendez@besco.mx"], "Odoo": ["gerardo.mendez@besco.mx"]
}
dest_oficina = mapeo_correos.get(oficina, ["gerardo.mendez@besco.mx"])
if "gerardo.mendez@besco.mx" not in dest_oficina: dest_oficina.append("gerardo.mendez@besco.mx")

st.info(f"📧 Destinatarios: {', '.join(dest_oficina)}")
correos_extra = st.text_input("Correos adicionales (separados por coma)")

if st.button("🚀 Generar y Enviar Reporte Final", type="primary"):
    with st.spinner("Construyendo documento PDF y procesando imágenes..."):
        pdf = BESCO_PDF()
        pdf.add_page()
        
        pdf.add_custom_section("Información General")
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 7, f"Cliente: {cliente} | Folio: {folio}", 0, 1)
        f_ejec_str = fecha_ejecucion.strftime('%d/%m/%Y')
        pdf.cell(0, 7, f"Fecha de Ejecución: {f_ejec_str} | Oficina: {oficina}", 0, 1)
        if sucursal: pdf.cell(0, 7, f"Sucursal: {sucursal}", 0, 1)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 7, f"ESTADO GLOBAL DE OPERACIÓN: {estado_op}/10", 0, 1)
        pdf.cell(0, 7, f"Técnico: {tecnico} | Supervisor: {supervisor}", 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 7, f"Servicio: {tipo_serv} ({referencia})", 0, 1); pdf.ln(5)

        for eq in equipos_data:
            if pdf.get_y() > 240: pdf.add_page()
            pdf.add_custom_section(f"EQUIPO {eq['numero']}: {eq['esp']}")
            
            valid_meds = {k: v for k, v in eq['meds'].items() if v}
            for k, v in valid_meds.items(): 
                pdf.cell(60, 6, f"{k}:", 1)
                pdf.cell(130, 6, f"{v}", 1, 1)
            if eq['otros']: 
                pdf.multi_cell(0, 6, f"Detalles: {eq['otros']}", 1)
                
            if eq['tag'] or eq['marca'] or eq['cap']: 
                pdf.set_font('Arial', 'B', 9)
                pdf.cell(0, 7, f"TAG: {eq['tag']} | Marca: {eq['marca']} | Cap: {eq['cap']}", 0, 1)
                pdf.set_font('Arial', '', 10)
                
            if eq['com']: 
                pdf.multi_cell(0, 6, f"Comentarios: {eq['com']}", 1)
                
            pdf.photo_grid(f"Antes (Eq. {eq['numero']})", eq['fa'], eq['numero'], "antes")
            pdf.photo_grid(f"Después (Eq. {eq['numero']})", eq['fd'], eq['numero'], "despues")
            pdf.ln(5)

        df_c = df_mat.dropna(subset=["Descripción"])
        if not df_c.empty:
            if pdf.get_y() > 220: pdf.add_page()
            pdf.add_custom_section("Materiales Utilizados")
            pdf.set_font('Arial', 'B', 9); pdf.cell(30, 7, "CANT.", 1, 0, 'C'); pdf.cell(160, 7, "DESCRIPCIÓN", 1, 1, 'C'); pdf.set_font('Arial', '', 9)
            for _, row in df_c.iterrows(): pdf.cell(30, 7, str(row["Cantidad"]), 1); pdf.cell(160, 7, str(row["Descripción"]), 1, 1)

        fotos_folio = [f for f in archivos_folio if f.type in ["image/jpeg", "image/png"]]
        if fotos_folio: pdf.folio_grid("FOLIO BESCO", fotos_folio)

        pdf_bytes = pdf.output(dest='S').encode('latin-1')

        pdfs_folio = [f for f in archivos_folio if f.type == "application/pdf"]
        if pdfs_folio:
            merger = PdfWriter()
            merger.append(io.BytesIO(pdf_bytes))
            for p in pdfs_folio: merger.append(p)
            out = io.BytesIO(); merger.write(out); pdf_bytes = out.getvalue()

        nom_archivo = f"Reporte_BESCO_Damian_{cliente}_{folio}.pdf".replace(" ", "_")
        
        correo_enviado = enviar_correo(pdf_bytes, cliente, folio, sucursal, oficina, nom_archivo, correos_extra, f_ejec_str, dest_oficina)
        
        if correo_enviado:
            st.success(f"✅ Reporte enviado a {oficina} y listo para descargar.")
        else:
            st.warning("⚠️ El PDF se generó correctamente, pero hubo un error al enviarlo por correo. Puedes descargarlo aquí abajo:")
        
    st.download_button("📥 Descargar PDF", data=pdf_bytes, file_name=nom_archivo, mime="application/pdf")
