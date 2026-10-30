import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF
import requests
from bs4 import BeautifulSoup
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(
    page_title="Protofab ERP | Finanzas y Cotizador 3D",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_FILE = "protofab_erp.db"

def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    with open("schema.sql", "r", encoding="utf-8") as f:
        c.executescript(f.read())
    
    c.execute("SELECT COUNT(*) FROM tasas_bcv")
    if c.fetchone()[0] == 0:
        tasas_demo = [
            ("2026-10-01", 45.20, 52.10, "Inicio de mes"),
            ("2026-10-10", 45.85, 53.00, "Ajuste BCV"),
            ("2026-10-20", 46.40, 54.20, "Cierre quincena"),
            (str(date.today()), 46.90, 54.80, "Tasa vigente actual")
        ]
        c.executemany("INSERT INTO tasas_bcv (fecha, tasa_bcv, tasa_paralelo, notas) VALUES (?, ?, ?, ?)", tasas_demo)

    c.execute("SELECT COUNT(*) FROM impresoras")
    if c.fetchone()[0] == 0:
        impresoras_default = [
            ("Creality K1 Max", 350, 2.40, 0.00052, 1),
            ("Creality Hi Combo (CFS)", 320, 2.20, 0.00045, 1),
            ("Creality Ender 3 Mod", 180, 1.80, 0.00030, 1),
            ("Granja General FDM", 250, 2.00, 0.00040, 1)
        ]
        # Check table columns or insert appropriately. Let's check schema for impresoras.
    conn.commit()
    conn.close()

init_db()

# Ensure impresoras table has costo_hora and desgaste_por_hora columns or handle them
def ensure_columns():
    conn = get_connection()
    c = conn.cursor()
    # Check if costo_hora_usd exists in impresoras
    c.execute("PRAGMA table_info(impresoras)")
    cols = [info[1] for info in c.fetchall()]
    if "costo_hora_usd" not in cols:
        try:
            c.execute("ALTER TABLE impresoras ADD COLUMN costo_hora_usd REAL DEFAULT 2.40")
        except:
            pass
    if "desgaste_por_hora" not in cols:
        try:
            c.execute("ALTER TABLE impresoras ADD COLUMN desgaste_por_hora REAL DEFAULT 0.00052")
        except:
            pass
    conn.commit()
    conn.close()

ensure_columns()

def consultar_tasa_bcv_online():
    tasa_oficial = None
    tasa_paralelo = None
    try:
        resp = requests.get("https://ve.dolarapi.com/v1/dolares", timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            for item in data:
                if item.get("fuente") == "oficial" and item.get("promedio"):
                    tasa_oficial = float(item["promedio"])
                elif item.get("fuente") == "paralelo" and item.get("promedio"):
                    tasa_paralelo = float(item["promedio"])
            if tasa_oficial and tasa_oficial > 0:
                if not tasa_paralelo:
                    tasa_paralelo = round(tasa_oficial * 1.15, 2)
                return round(tasa_oficial, 4), round(tasa_paralelo, 4), "API Oficial BCV (ve.dolarapi.com)"
    except Exception:
        pass

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp_bcv = requests.get("https://www.bcv.org.ve", headers=headers, verify=False, timeout=10)
        if resp_bcv.status_code == 200:
            soup = BeautifulSoup(resp_bcv.text, "html.parser")
            div_dolar = soup.find("div", {"id": "dolar"})
            if div_dolar:
                strong_tag = div_dolar.find("strong")
                if strong_tag:
                    texto_valor = strong_tag.text.strip().replace(".", "").replace(",", ".")
                    match = re.search(r"\d+(\.\d+)?", texto_valor)
                    if match:
                        tasa_oficial = float(match.group(0))
                        tasa_paralelo = round(tasa_oficial * 1.15, 2)
                        return round(tasa_oficial, 4), tasa_paralelo, "Web Directa BCV (bcv.org.ve)"
    except Exception as e:
        return None, None, str(e)

    return None, None, "Sin respuesta"

def obtener_tasa_bcv_actual():
    conn = get_connection()
    df = pd.read_sql_query("SELECT tasa_bcv, tasa_paralelo, fecha FROM tasas_bcv ORDER BY fecha DESC, id DESC LIMIT 1", conn)
    conn.close()
    if not df.empty:
        return float(df.iloc[0]["tasa_bcv"]), float(df.iloc[0]["tasa_paralelo"]), df.iloc[0]["fecha"]
    return 46.90, 54.80, str(date.today())

# PDF Generator EXCLUSIVO EN USD (Sin Bolívares para no confundir al cliente)
def generar_pdf_cotizacion_usd(datos_oferta):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado Corporativo Protofab
    pdf.set_fill_color(18, 28, 45)
    pdf.rect(0, 0, 210, 38, 'F')
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_xy(12, 10)
    pdf.cell(100, 10, "PROTOFAB", ln=True)
    
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(12, 21)
    pdf.cell(100, 6, "Manufactura Digital, Diseño CAD 3D e Ingeniería | Maturín, Venezuela", ln=True)
    
    # Cuadro de Código de Oferta
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(140, 10)
    pdf.cell(58, 8, f"OFERTA: {datos_oferta['codigo']}", align="R", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(140, 18)
    pdf.cell(58, 6, f"Fecha: {datos_oferta['fecha']}", align="R", ln=True)

    # Datos del Cliente
    pdf.set_text_color(30, 30, 30)
    pdf.set_xy(12, 46)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "DATOS DEL CLIENTE:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Cliente / Empresa: {datos_oferta['cliente']}", ln=True)
    pdf.cell(0, 6, f"RIF / Cédula: {datos_oferta['rif']}   |   Contacto: {datos_oferta['telefono']}", ln=True)
    pdf.cell(0, 6, f"Categoría de Servicio: {datos_oferta['categoria']}", ln=True)
    pdf.ln(5)

    # Tabla de Ítems (EXCLUSIVO EN USD)
    pdf.set_fill_color(230, 235, 242)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(135, 9, "Descripción del Servicio / Proyecto", border=1, fill=True)
    pdf.cell(55, 9, "Monto Total USD ($)", border=1, align="R", fill=True, ln=True)

    pdf.set_font("Helvetica", "", 10)
    x_start = pdf.get_x()
    y_start = pdf.get_y()
    pdf.multi_cell(135, 7, datos_oferta['descripcion'], border=1)
    y_end = pdf.get_y()
    alto_fila = y_end - y_start

    pdf.set_xy(x_start + 135, y_start)
    pdf.cell(55, alto_fila, f"${datos_oferta['total_usd']:,.2f}", border=1, align="R", ln=True)

    pdf.ln(4)

    # Desglose de Totales (Solo USD)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(135, 7, "", border=0)
    pdf.cell(35, 7, "Subtotal Sin IVA:", border=1, align="R")
    pdf.cell(20, 7, f"${datos_oferta['subtotal_usd']:,.2f}", border=1, align="R", ln=True)

    if datos_oferta['es_facturable']:
        pdf.cell(135, 7, "", border=0)
        pdf.cell(35, 7, f"IVA ({datos_oferta['iva_pct']}%):", border=1, align="R")
        pdf.cell(20, 7, f"${datos_oferta['iva_usd']:,.2f}", border=1, align="R", ln=True)

    pdf.set_fill_color(18, 28, 45)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(135, 9, "", border=0)
    pdf.cell(35, 9, "TOTAL A PAGAR:", border=1, align="R", fill=True)
    pdf.cell(20, 9, f"${datos_oferta['total_usd']:,.2f}", border=1, align="R", fill=True, ln=True)

    # Condiciones Comerciales
    pdf.set_text_color(30, 30, 30)
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "CONDICIONES COMERCIALES:", ln=True)
    pdf.set_font("Helvetica", "", 9)
    Modalidad = f"Factura Fiscal (Incluye IVA {datos_oferta['iva_pct']}%)" if datos_oferta['es_facturable'] else "Nota de Entrega / Control Interno"
    pdf.multi_cell(0, 5, f"""1. Modalidad de documento: {Modalidad}.
2. Moneda de cobro: Dólares estadounidenses (USD).
3. Condiciones de pago: 50% de anticipo para iniciar producción / modelado CAD y 50% contra entrega.
4. Validez de la oferta: 5 días continuos.""")

    return bytes(pdf.output())

tasa_actual, tasa_par_actual, fecha_tasa = obtener_tasa_bcv_actual()

with st.sidebar:
    st.title("⚙️ PROTOFAB ERP")
    st.caption("Sistema Bimonetario & Cotizador 3D")
    st.metric("💵 Tasa BCV Vigente", f"Bs. {tasa_actual:,.2f}", f"Fecha: {fecha_tasa}")
    
    if st.button("🔄 Sincronizar BCV Hoy", use_container_width=True):
        bcv_v, par_v, fuente_v = consultar_tasa_bcv_online()
        if bcv_v:
            conn = get_connection()
            conn.execute(
                "INSERT OR REPLACE INTO tasas_bcv (fecha, tasa_bcv, tasa_paralelo, notas) VALUES (?, ?, ?, ?)",
                (str(date.today()), bcv_v, par_v, f"API: {fuente_v}")
            )
            conn.commit()
            conn.close()
            st.success(f"✅ BCV actualizado: Bs. {bcv_v:,.2f}")
            st.rerun()
        else:
            st.error(f"⚠️ Error: {fuente_v}")

    st.divider()
    modulo = st.radio(
        "Navegación Principal",
        [
            "📊 1. Dashboard Directivo",
            "💰 2. Registrar Ingresos",
            "📉 3. Registrar Egresos",
            "🧮 4. Cotizador 3D (Modelo Exacto)",
            "📋 5. Deudas (CxC / CxP)",
            "🏦 6. Tasas BCV & Limpieza"
        ]
    )

if modulo == "📊 1. Dashboard Directivo":
    st.header("📊 Dashboard Financiero, Fiscal y de Liquidez - Protofab")
    conn = get_connection()
    df_ing = pd.read_sql_query("SELECT * FROM ingresos", conn)
    df_egr = pd.read_sql_query("SELECT * FROM egresos", conn)
    df_deu = pd.read_sql_query("SELECT * FROM deudas", conn)
    conn.close()

    ing_bruto_usd = df_ing["total_usd_bcv"].sum() if not df_ing.empty else 0.0
    ing_base_usd = df_ing["base_imponible_usd"].sum() if not df_ing.empty else 0.0
    iva_debito_usd = df_ing["iva_debito_usd"].sum() if not df_ing.empty else 0.0
    retenciones_usd = df_ing["retencion_iva_usd"].sum() if not df_ing.empty else 0.0

    egr_bruto_usd = df_egr["total_usd_bcv"].sum() if not df_egr.empty else 0.0
    egr_base_usd = df_egr["costo_base_usd"].sum() if not df_egr.empty else 0.0
    iva_credito_usd = df_egr["iva_credito_usd"].sum() if not df_egr.empty else 0.0

    utilidad_operativa_usd = ing_base_usd - egr_base_usd
    iva_por_pagar_usd = max(0.0, iva_debito_usd - iva_credito_usd - retenciones_usd)
    iva_por_pagar_ves = iva_por_pagar_usd * tasa_actual

    liquidez_total_usd = ing_bruto_usd - egr_bruto_usd
    cxc_pendiente = df_deu[df_deu["tipo"] == "Por Cobrar (Cliente)"]["saldo_pendiente_usd"].sum() if not df_deu.empty else 0.0
    cxp_pendiente = df_deu[df_deu["tipo"] == "Por Pagar (Proveedor/Socio)"]["saldo_pendiente_usd"].sum() if not df_deu.empty else 0.0
    liquidez_libre_real = liquidez_total_usd - iva_por_pagar_usd - cxp_pendiente

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("💵 Liquidez Total", f"${liquidez_total_usd:,.2f}", f"Bs. {liquidez_total_usd*tasa_actual:,.2f}")
    col2.metric("🛡️ Liquidez Libre Real", f"${liquidez_libre_real:,.2f}", "Libre de IVA y CxP")
    col3.metric("📈 Utilidad Neta", f"${utilidad_operativa_usd:,.2f}", f"Base Ing: ${ing_base_usd:,.2f}")
    col4.metric("🏛️ Provisión SENIAT", f"${iva_por_pagar_usd:,.2f}", f"Bs. {iva_por_pagar_ves:,.2f}")
    col5.metric("🤝 Cartera CxC vs CxP", f"Cobrar: ${cxc_pendiente:,.2f}", f"Pagar: -${cxp_pendiente:,.2f}")

    st.divider()
    st.subheader("🏦 Liquidez por Billetera")
    cuentas = ["Banco VES", "Efectivo USD", "Binance USDT / Zelle"]
    cols_cta = st.columns(3)
    for idx, cta in enumerate(cuentas):
        ent = df_ing[df_ing["cuenta_destino"] == cta]["total_usd_bcv"].sum() if not df_ing.empty else 0.0
        sal = df_egr[df_egr["cuenta_origen"] == cta]["total_usd_bcv"].sum() if not df_egr.empty else 0.0
        saldo_cta = ent - sal
        cols_cta[idx].info(f"""**{cta}**\n\n### ${saldo_cta:,.2f} USD\n*(Eq. Bs. {saldo_cta*tasa_actual:,.2f})*""")

elif modulo == "💰 2. Registrar Ingresos":
    st.header("💰 Registro de Ingresos")
    with st.form("form_ingreso"):
        c1, c2, c3 = st.columns(3)
        fecha_cobro = c1.date_input("Fecha de Cobro", value=date.today())
        cliente = c2.text_input("Cliente / Empresa")
        categoria = c3.selectbox("Categoría", ["Impresión 3D bajo demanda", "Diseño 3D", "Diseño e impresión 3D", "Proyecto especial", "Otro"])

        c4, c5, c6, c7 = st.columns(4)
        cuenta_destino = c4.selectbox("Cuenta Destino", ["Banco VES", "Efectivo USD", "Binance USDT / Zelle"])
        moneda_orig = c5.selectbox("Moneda", ["USD", "VES"])
        monto_orig = c6.number_input("Monto Cobrado", min_value=0.0, step=1.0)
        tasa_op = c7.number_input("Tasa BCV del Día", min_value=1.0, value=tasa_actual, step=0.1)

        c8, c9, c10 = st.columns([1, 1, 2])
        es_facturable = c8.selectbox("Facturable (IVA 16%)?", ["No", "Sí"])
        retencion_usd = c9.number_input("Retención IVA (USD)", min_value=0.0, value=0.0)
        descripcion = c10.text_input("Descripción / Nº Factura")

        if st.form_submit_button("💾 Guardar Ingreso") and monto_orig > 0:
            total_ves = monto_orig * tasa_op if moneda_orig == "USD" else monto_orig
            total_usd = monto_orig if moneda_orig == "USD" else monto_orig / tasa_op
            fact_int = 1 if es_facturable == "Sí" else 0
            base_usd = (total_usd / 1.16) if fact_int == 1 else total_usd
            iva_usd = (total_usd - base_usd) if fact_int == 1 else 0.0
            iva_ves = iva_usd * tasa_op

            conn = get_connection()
            conn.execute("""INSERT INTO ingresos 
                (fecha_cobro, cliente, descripcion, categoria, cuenta_destino, moneda_original, monto_original, tasa_bcv_dia, total_ves, total_usd_bcv, es_facturable, base_imponible_usd, iva_debito_usd, iva_debito_ves, retencion_iva_usd, notas)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(fecha_cobro), cliente, descripcion, categoria, cuenta_destino, moneda_orig, monto_orig, tasa_op, total_ves, total_usd, fact_int, base_usd, iva_usd, iva_ves, retencion_usd, ""))
            conn.commit()
            conn.close()
            st.success(f"✅ Ingreso guardado: ${total_usd:,.2f} USD")
            st.rerun()

    conn = get_connection()
    df_ing = pd.read_sql_query("SELECT * FROM ingresos ORDER BY id DESC", conn)
    conn.close()
    st.dataframe(df_ing, use_container_width=True)

    if not df_ing.empty:
        with st.expander("🗑️ Eliminar Ingreso"):
            op = {f"ID #{r['id']} | {r['fecha_cobro']} | {r['cliente']} - ${r['total_usd_bcv']:,.2f}": r['id'] for _, r in df_ing.iterrows()}
            sel = st.selectbox("Seleccionar:", list(op.keys()))
            if st.button("🚨 Eliminar Ingreso", type="primary"):
                conn = get_connection()
                conn.execute("DELETE FROM ingresos WHERE id = ?", (op[sel],))
                conn.commit()
                conn.close()
                st.rerun()

elif modulo == "📉 3. Registrar Egresos":
    st.header("📉 Registro de Egresos")
    with st.form("form_egreso"):
        c1, c2, c3 = st.columns(3)
        fecha_pago = c1.date_input("Fecha de Pago", value=date.today())
        proveedor = c2.text_input("Proveedor / Beneficiario")
        categoria = c3.selectbox("Categoría", ["Materiales", "Repuestos", "Nómina", "Herramientas", "Utilidades", "Reparaciones", "Publicidad", "Otros"])

        c4, c5, c6, c7 = st.columns(4)
        cuenta_origen = c4.selectbox("Cuenta Origen", ["Banco VES", "Efectivo USD", "Binance USDT / Zelle"])
        moneda_orig = c5.selectbox("Moneda", ["USD", "VES"])
        monto_orig = c6.number_input("Monto Pagado", min_value=0.0, step=1.0)
        tasa_op = c7.number_input("Tasa BCV del Día", min_value=1.0, value=tasa_actual, step=0.1)

        c8, c9 = st.columns([1, 3])
        es_facturable = c8.selectbox("Con Factura (Crédito IVA)?", ["No", "Sí"])
        concepto = c9.text_input("Detalle / Nº Factura")

        if st.form_submit_button("💾 Guardar Egreso") and monto_orig > 0:
            total_ves = monto_orig * tasa_op if moneda_orig == "USD" else monto_orig
            total_usd = monto_orig if moneda_orig == "USD" else monto_orig / tasa_op
            fact_int = 1 if es_facturable == "Sí" else 0
            base_usd = (total_usd / 1.16) if fact_int == 1 else total_usd
            iva_usd = (total_usd - base_usd) if fact_int == 1 else 0.0
            iva_ves = iva_usd * tasa_op

            conn = get_connection()
            conn.execute("""INSERT INTO egresos 
                (fecha_pago, proveedor_beneficiario, concepto, categoria, cuenta_origen, moneda_original, monto_original, tasa_bcv_dia, total_ves, total_usd_bcv, es_facturable, costo_base_usd, iva_credito_usd, iva_credito_ves, notas)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(fecha_pago), proveedor, concepto, categoria, cuenta_origen, moneda_orig, monto_orig, tasa_op, total_ves, total_usd, fact_int, base_usd, iva_usd, iva_ves, ""))
            conn.commit()
            conn.close()
            st.success(f"✅ Egreso guardado: ${total_usd:,.2f} USD")
            st.rerun()

    conn = get_connection()
    df_egr = pd.read_sql_query("SELECT * FROM egresos ORDER BY id DESC", conn)
    conn.close()
    st.dataframe(df_egr, use_container_width=True)

    if not df_egr.empty:
        with st.expander("🗑️ Eliminar Egreso"):
            op_eg = {f"ID #{r['id']} | {r['fecha_pago']} | {r['proveedor_beneficiario']} - ${r['total_usd_bcv']:,.2f}": r['id'] for _, r in df_egr.iterrows()}
            sel_eg = st.selectbox("Seleccionar:", list(op_eg.keys()))
            if st.button("🚨 Eliminar Egreso", type="primary"):
                conn = get_connection()
                conn.execute("DELETE FROM egresos WHERE id = ?", (op_eg[sel_eg],))
                conn.commit()
                conn.close()
                st.rerun()

# PDF Generator EXCLUSIVO EN USD con múltiples ítems y logo oficial
def generar_pdf_cotizacion_usd(datos_oferta):
    pdf = FPDF()
    pdf.add_page()
    
    # 1. ENCABEZADO CORPORATIVO CON LOGO Y RIF
    pdf.set_fill_color(18, 28, 45)  # Azul oscuro oscuro
    pdf.rect(0, 0, 210, 42, 'F')
    
    # Insertar el logo de Protofab en el encabezado
    try:
        # Se asume que guardaste el logo adjunto como "image_2.png" en tu carpeta
        pdf.image("image_2.png", x=12, y=6, w=22) 
    except Exception:
        # Si no se encuentra la imagen, se dibuja un placeholder con texto para no tumbar el script
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(12, 12)
        pdf.cell(30, 10, "[LOGO]")

    # Texto del encabezado
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(38, 10)
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(100, 10, "PROTOFAB", ln=True)
    
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(38, 20)
    pdf.cell(100, 5, "Manufactura Digital, Diseño CAD 3D e Ingeniería", ln=True)
    pdf.set_xy(38, 25)
    pdf.cell(100, 5, "Maturín, Monagas, Venezuela   |   RIF: J-50769354-6", ln=True)
    
    # Cuadro de Código de Oferta (Totalmente Editable)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(140, 10)
    pdf.cell(58, 8, f"OFERTA: {datos_oferta['codigo']}", align="R", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(140, 18)
    pdf.cell(58, 6, f"Fecha: {datos_oferta['fecha']}", align="R", ln=True)
    pdf.set_xy(140, 24)
    pdf.cell(58, 6, "Moneda: USD ($)", align="R", ln=True)

    # 2. DATOS DEL CLIENTE
    pdf.set_text_color(30, 30, 30)
    pdf.set_xy(12, 48)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "DATOS DEL CLIENTE:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Cliente / Empresa: {datos_oferta['cliente']}", ln=True)
    pdf.cell(0, 6, f"RIF / Cédula: {datos_oferta['rif']}   |   Contacto: {datos_oferta['telefono']}", ln=True)
    pdf.cell(0, 6, f"Categoría de Servicio: {datos_oferta['categoria']}", ln=True)
    pdf.ln(5)

    # 3. TABLA DE MÚLTIPLES ÍTEMS (EXCLUSIVO EN USD)
    pdf.set_fill_color(230, 235, 242)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(12, 8, "Cant.", border=1, align="C", fill=True)
    pdf.cell(123, 8, "Descripción del Servicio / Pieza / Proyecto", border=1, fill=True)
    pdf.cell(25, 8, "P. Unitario ($)", border=1, align="R", fill=True)
    pdf.cell(28, 8, "Subtotal ($)", border=1, align="R", fill=True, ln=True)

    pdf.set_font("Helvetica", "", 9)
    for item in datos_oferta['items']:
        x_start = pdf.get_x()
        y_start = pdf.get_y()
        
        # Guardar cantidad y descripcion multilínea
        pdf.cell(12, 7, str(item['cant']), border=0, align="C")
        
        # Procesar descripción con multi_cell
        pdf.set_xy(x_start + 12, y_start)
        pdf.multi_cell(123, 6, item['desc'], border=0)
        y_end = pdf.get_y()
        alto_fila = max(7, y_end - y_start)
        
        # Volver al flujo para dibujar bordes del recuadro
        pdf.set_xy(x_start, y_start)
        pdf.cell(12, alto_fila, "", border=1)
        pdf.cell(123, alto_fila, "", border=1)
        pdf.cell(25, alto_fila, f"${item['pu']:,.2f}", border=1, align="R")
        pdf.cell(28, alto_fila, f"${item['sub']:,.2f}", border=1, align="R", ln=True)

    pdf.ln(4)

    # Desglose de Totales (Solo USD)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(135, 7, "", border=0)
    pdf.cell(35, 7, "Subtotal Sin IVA:", border=1, align="R")
    pdf.cell(20, 7, f"${datos_oferta['subtotal_usd']:,.2f}", border=1, align="R", ln=True)

    if datos_oferta['es_facturable']:
        pdf.cell(135, 7, "", border=0)
        pdf.cell(35, 7, f"IVA ({datos_oferta['iva_pct']}%):", border=1, align="R")
        pdf.cell(20, 7, f"${datos_oferta['iva_usd']:,.2f}", border=1, align="R", ln=True)

    pdf.set_fill_color(18, 28, 45)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(135, 9, "", border=0)
    pdf.cell(35, 9, "TOTAL A PAGAR:", border=1, align="R", fill=True)
    pdf.cell(20, 9, f"${datos_oferta['total_usd']:,.2f}", border=1, align="R", fill=True, ln=True)

    # 4. CONDICIONES COMERCIALES
    pdf.set_text_color(30, 30, 30)
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "CONDICIONES COMERCIALES:", ln=True)
    pdf.set_font("Helvetica", "", 9)
    Modalidad = f"Factura Fiscal (Incluye IVA {datos_oferta['iva_pct']}%)" if datos_oferta['es_facturable'] else "Nota de Entrega / Control Interno"
    pdf.multi_cell(0, 5, f"""1. Modalidad de documento: {Modalidad}.
2. Moneda de cobro: Dólares estadounidenses (USD).
3. Condiciones de pago: 50% de anticipo para iniciar producción / modelado CAD y 50% contra entrega.
4. Los pagos en Bolívares (VES) se calcularán a la tasa oficial del BCV del día de la transacción.
5. Validez de la oferta: 5 días continuos.""")

    return bytes(pdf.output())

elif modulo == "📋 5. Deudas (CxC / CxP)":
    st.header("📋 Cuentas por Cobrar y por Pagar")
    with st.form("form_deuda"):
        c1, c2, c3, c4 = st.columns(4)
        tipo_d = c1.selectbox("Tipo", ["Por Cobrar (Cliente)", "Por Pagar (Proveedor/Socio)"])
        contraparte = c2.text_input("Contraparte")
        fecha_venc = c3.date_input("Vencimiento", value=date.today())
        concepto_d = c4.text_input("Concepto")

        c5, c6 = st.columns(2)
        monto_tot = c5.number_input("Monto Total ($)", min_value=0.0, step=5.0)
        monto_abo = c6.number_input("Abonado ($)", min_value=0.0, step=5.0)

        if st.form_submit_button("💾 Guardar Deuda") and monto_tot > 0:
            saldo = max(0.0, monto_tot - monto_abo)
            estado_d = "Pagado" if saldo == 0 else ("Abono Parcial" if monto_abo > 0 else "Pendiente")
            conn = get_connection()
            conn.execute("INSERT INTO deudas (fecha_registro, fecha_vencimiento, tipo, contraparte, concepto, monto_total_usd, monto_abonado_usd, saldo_pendiente_usd, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (str(date.today()), str(fecha_venc), tipo_d, contraparte, concepto_d, monto_tot, monto_abo, saldo, estado_d))
            conn.commit()
            conn.close()
            st.success("✅ Deuda guardada.")
            st.rerun()

    conn = get_connection()
    df_d = pd.read_sql_query("SELECT * FROM deudas ORDER BY id DESC", conn)
    conn.close()
    if not df_d.empty:
        df_d["equivalente_hoy_ves"] = df_d["saldo_pendiente_usd"] * tasa_actual
    st.dataframe(df_d, use_container_width=True)

    if not df_d.empty:
        with st.expander("🗑️ Eliminar Deuda"):
            op_deu = {f"ID #{r['id']} | {r['contraparte']} - ${r['saldo_pendiente_usd']:,.2f}": r['id'] for _, r in df_d.iterrows()}
            sel_deu = st.selectbox("Seleccionar:", list(op_deu.keys()))
            if st.button("🚨 Eliminar Deuda", type="primary"):
                conn = get_connection()
                conn.execute("DELETE FROM deudas WHERE id = ?", (op_deu[sel_deu],))
                conn.commit()
                conn.close()
                st.rerun()

elif modulo == "🏦 6. Tasas BCV & Limpieza":
    st.header("🏦 Tasas BCV y Mantenimiento")
    if st.button("⚡ Sincronizar Tasa BCV Ahora", type="primary"):
        bcv_v, par_v, fuente_v = consultar_tasa_bcv_online()
        if bcv_v:
            conn = get_connection()
            conn.execute("INSERT OR REPLACE INTO tasas_bcv (fecha, tasa_bcv, tasa_paralelo, notas) VALUES (?, ?, ?, ?)",
                         (str(date.today()), bcv_v, par_v, f"API: {fuente_v}"))
            conn.commit()
            conn.close()
            st.success(f"✅ Tasa actualizada: Bs. {bcv_v:,.2f}")
            st.rerun()
        else:
            st.error(f"Error: {fuente_v}")

    conn = get_connection()
    st.dataframe(pd.read_sql_query("SELECT * FROM tasas_bcv ORDER BY fecha DESC", conn), use_container_width=True)

    st.divider()
    if st.button("🗑️ Vaciar Todos los Registros Operativos"):
        conn = get_connection()
        conn.execute("DELETE FROM ingresos")
        conn.execute("DELETE FROM egresos")
        conn.execute("DELETE FROM ofertas")
        conn.execute("DELETE FROM deudas")
        conn.commit()
        conn.close()
        st.success("✅ Sistema limpiado.")
        st.rerun()
