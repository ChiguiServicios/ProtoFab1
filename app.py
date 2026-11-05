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
    
    c.execute("""CREATE TABLE IF NOT EXISTS tasas_bcv (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha DATE UNIQUE NOT NULL,
        tasa_bcv REAL NOT NULL,
        tasa_paralelo REAL DEFAULT 0.0,
        notas TEXT
    );""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS ingresos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_cobro DATE NOT NULL,
        cliente TEXT NOT NULL,
        descripcion TEXT NOT NULL,
        categoria TEXT NOT NULL,
        cuenta_destino TEXT NOT NULL,
        moneda_original TEXT NOT NULL,
        monto_original REAL NOT NULL,
        tasa_bcv_dia REAL NOT NULL,
        total_ves REAL NOT NULL,
        total_usd_bcv REAL NOT NULL,
        es_facturable INTEGER NOT NULL DEFAULT 0,
        base_imponible_usd REAL NOT NULL,
        iva_debito_usd REAL NOT NULL,
        iva_debito_ves REAL NOT NULL,
        retencion_iva_usd REAL DEFAULT 0.0,
        notas TEXT
    );""")

    c.execute("""CREATE TABLE IF NOT EXISTS egresos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_pago DATE NOT NULL,
        proveedor_beneficiario TEXT NOT NULL,
        concepto TEXT NOT NULL,
        categoria TEXT NOT NULL,
        cuenta_origen TEXT NOT NULL,
        moneda_original TEXT NOT NULL,
        monto_original REAL NOT NULL,
        tasa_bcv_dia REAL NOT NULL,
        total_ves REAL NOT NULL,
        total_usd_bcv REAL NOT NULL,
        es_facturable INTEGER NOT NULL DEFAULT 0,
        costo_base_usd REAL NOT NULL,
        iva_credito_usd REAL NOT NULL,
        iva_credito_ves REAL NOT NULL,
        notas TEXT
    );""")

    c.execute("""CREATE TABLE IF NOT EXISTS inventario_materiales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo_material TEXT NOT NULL,
        nombre_marca TEXT NOT NULL,
        color_descripcion TEXT NOT NULL,
        stock_cantidad REAL NOT NULL,
        unidad TEXT NOT NULL,
        costo_unitario_usd REAL NOT NULL
    );""")

    c.execute("""CREATE TABLE IF NOT EXISTS deudas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_registro DATE NOT NULL,
        fecha_vencimiento DATE,
        tipo TEXT NOT NULL,
        contraparte TEXT NOT NULL,
        concepto TEXT NOT NULL,
        monto_total_usd REAL NOT NULL,
        monto_abonado_usd REAL DEFAULT 0.0,
        saldo_pendiente_usd REAL NOT NULL,
        estado TEXT DEFAULT 'Pendiente'
    );""")

    conn.commit()
    conn.close()

init_db()

def consultar_tasa_bcv_online():
    tasa_oficial, tasa_paralelo = None, None
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
                return round(tasa_oficial, 4), round(tasa_paralelo, 4), "API Oficial BCV"
    except Exception:
        pass
    return None, None, "Sin respuesta"

def obtener_tasa_bcv_actual():
    conn = get_connection()
    df = pd.read_sql_query("SELECT tasa_bcv, tasa_paralelo, fecha FROM tasas_bcv ORDER BY fecha DESC, id DESC LIMIT 1", conn)
    conn.close()
    if not df.empty:
        return float(df.iloc[0]["tasa_bcv"]), float(df.iloc[0]["tasa_paralelo"]), df.iloc[0]["fecha"]
    return 46.90, 54.80, str(date.today())

def generar_pdf_cotizacion_usd(datos_oferta):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_fill_color(18, 28, 45)
    pdf.rect(0, 0, 210, 42, 'F')
    
    try:
        pdf.image("image_2.png", x=12, y=6, w=22)
    except Exception:
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(12, 12)
        pdf.cell(30, 10, "[LOGO]")

    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(38, 10)
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(100, 10, "PROTOFAB", ln=True)
    
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(38, 20)
    pdf.cell(100, 5, "Manufactura Digital, Diseño CAD 3D e Ingeniería", ln=True)
    pdf.set_xy(38, 25)
    pdf.cell(100, 5, "Maturín, Monagas, Venezuela   |   RIF: J-50769354-6", ln=True)
    
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(140, 10)
    pdf.cell(58, 8, f"OFERTA: {datos_oferta['codigo']}", align="R", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(140, 18)
    pdf.cell(58, 6, f"Fecha: {datos_oferta['fecha']}", align="R", ln=True)
    pdf.set_xy(140, 24)
    pdf.cell(58, 6, "Moneda: USD ($)", align="R", ln=True)

    pdf.set_text_color(30, 30, 30)
    pdf.set_xy(12, 48)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "DATOS DEL CLIENTE:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Cliente / Empresa: {datos_oferta['cliente']}", ln=True)
    pdf.cell(0, 6, f"RIF / Cédula: {datos_oferta['rif']}   |   Contacto: {datos_oferta['telefono']}", ln=True)
    pdf.cell(0, 6, f"Categoría de Servicio: {datos_oferta['categoria']}", ln=True)
    pdf.ln(5)

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
        
        pdf.cell(12, 7, str(item['cant']), border=0, align="C")
        pdf.set_xy(x_start + 12, y_start)
        pdf.multi_cell(123, 6, item['desc'], border=0)
        y_end = pdf.get_y()
        alto_fila = max(7, y_end - y_start)
        
        pdf.set_xy(x_start, y_start)
        pdf.cell(12, alto_fila, "", border=1)
        pdf.cell(123, alto_fila, "", border=1)
        pdf.cell(25, alto_fila, f"${item['pu']:,.2f}", border=1, align="R")
        pdf.cell(28, alto_fila, f"${item['sub']:,.2f}", border=1, align="R", ln=True)

    pdf.ln(4)

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

tasa_actual, tasa_par_actual, fecha_tasa = obtener_tasa_bcv_actual()

with st.sidebar:
    st.title("⚙️ PROTOFAB ERP")
    st.caption("Sistema Bimonetario & Cotizador 3D")
    st.metric("💵 Tasa BCV Vigente", f"Bs. {tasa_actual:,.2f}", f"Fecha: {fecha_tasa}")
    
    if st.button("🔄 Sincronizar BCV Hoy", use_container_width=True):
        bcv_v, par_v, fuente_v = consultar_tasa_bcv_online()
        if bcv_v:
            conn = get_connection()
            conn.execute("INSERT OR REPLACE INTO tasas_bcv (fecha, tasa_bcv, tasa_paralelo, notas) VALUES (?, ?, ?, ?)",
                         (str(date.today()), bcv_v, par_v, f"API: {fuente_v}"))
            conn.commit()
            conn.close()
            st.success(f"✅ BCV actualizado: Bs. {bcv_v:,.2f}")
            st.rerun()

    st.divider()
    modulo = st.radio(
        "Navegación Principal",
        [
            "📊 1. Dashboard Directivo",
            "💰 2. Registrar Ingresos",
            "📉 3. Registrar Egresos",
            "📦 4. Inventario de Materiales",
            "🧮 5. Cotizador 3D (Múltiples Ítems)",
            "📋 6. Deudas (CxC / CxP)",
            "🏦 7. Tasas BCV & Limpieza"
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
    
    egr_bruto_usd = df_egr["total_usd_bcv"].sum() if not df_egr.empty else 0.0
    egr_base_usd = df_egr["costo_base_usd"].sum() if not df_egr.empty else 0.0
    iva_credito_usd = df_egr["iva_credito_usd"].sum() if not df_egr.empty else 0.0

    utilidad_operativa_usd = ing_base_usd - egr_base_usd
    iva_por_pagar_usd = max(0.0, iva_debito_usd - iva_credito_usd)
    liquidez_total_usd = ing_bruto_usd - egr_bruto_usd
    cxc_pendiente = df_deu[df_deu["tipo"] == "Por Cobrar (Cliente)"]["saldo_pendiente_usd"].sum() if not df_deu.empty else 0.0
    cxp_pendiente = df_deu[df_deu["tipo"] == "Por Pagar (Proveedor/Socio)"]["saldo_pendiente_usd"].sum() if not df_deu.empty else 0.0

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("💵 Liquidez Total", f"${liquidez_total_usd:,.2f}", f"Bs. {liquidez_total_usd*tasa_actual:,.2f}")
    col2.metric("🛡️ Liquidez Real", f"${liquidez_total_usd - iva_por_pagar_usd:,.2f}")
    col3.metric("📈 Utilidad Neta", f"${utilidad_operativa_usd:,.2f}")
    col4.metric("🏛️ Provisión SENIAT", f"${iva_por_pagar_usd:,.2f}")
    col5.metric("🤝 CxC vs CxP", f"${cxc_pendiente:,.2f} / -${cxp_pendiente:,.2f}")

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

            conn = get_connection()
            conn.execute("""INSERT INTO ingresos 
                (fecha_cobro, cliente, descripcion, categoria, cuenta_destino, moneda_original, monto_original, tasa_bcv_dia, total_ves, total_usd_bcv, es_facturable, base_imponible_usd, iva_debito_usd, iva_debito_ves, retencion_iva_usd, notas)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(fecha_cobro), cliente, descripcion, categoria, cuenta_destino, moneda_orig, monto_orig, tasa_op, total_ves, total_usd, fact_int, base_usd, iva_usd, iva_usd*tasa_op, retencion_usd, ""))
            conn.commit()
            conn.close()
            st.success(f"✅ Ingreso guardado: ${total_usd:,.2f} USD")
            st.rerun()

    conn = get_connection()
    df_ing = pd.read_sql_query("SELECT * FROM ingresos ORDER BY id DESC", conn)
    conn.close()
    st.dataframe(df_ing, use_container_width=True)

elif modulo == "📉 3. Registrar Egresos":
    st.header("📉 Registro de Egresos y Costos Operativos")
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

            conn = get_connection()
            conn.execute("""INSERT INTO egresos 
                (fecha_pago, proveedor_beneficiario, concepto, categoria, cuenta_origen, moneda_original, monto_original, tasa_bcv_dia, total_ves, total_usd_bcv, es_facturable, costo_base_usd, iva_credito_usd, iva_credito_ves, notas)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(fecha_pago), proveedor, concepto, categoria, cuenta_origen, moneda_orig, monto_orig, tasa_op, total_ves, total_usd, fact_int, base_usd, iva_usd, iva_usd*tasa_op, ""))
            conn.commit()
            conn.close()
            st.success(f"✅ Egreso guardado: ${total_usd:,.2f} USD")
            st.rerun()

    conn = get_connection()
    df_egr = pd.read_sql_query("SELECT * FROM egresos ORDER BY id DESC", conn)
    conn.close()
    st.dataframe(df_egr, use_container_width=True)

elif modulo == "📦 4. Inventario de Materiales":
    st.header("📦 Control de Inventario (Filamentos y Consumibles Varios)")
    
    with st.form("form_inventario"):
        c1, c2, c3 = st.columns(3)
        tipo_mat = c1.selectbox("Tipo de Material", ["Filamento", "Consumible (Tornillos/Insertos/Imanes/Pegamento)"])
        nombre_marca = c2.text_input("Nombre / Marca (ej: Sunlu PLA, Inserto M3)")
        color_desc = c3.text_input("Color / Descripción (ej: Negro Mate, Latón M3x5)")

        c4, c5, c6 = st.columns(3)
        stock_cant = c4.number_input("Cantidad a Cargar", min_value=0.0, value=1000.0, step=10.0)
        unidad_med = c5.selectbox("Unidad", ["Gramos", "Unidades", "Metros"])
        costo_unit = c6.number_input("Costo Unitario ($)", min_value=0.0, value=18.0, step=0.5)

        if st.form_submit_button("➕ Registrar / Cargar Material"):
            conn = get_connection()
            conn.execute("""INSERT INTO inventario_materiales (tipo_material, nombre_marca, color_descripcion, stock_cantidad, unidad, costo_unitario_usd)
                VALUES (?, ?, ?, ?, ?, ?)""", (tipo_mat, nombre_marca, color_desc, stock_cant, unidad_med, costo_unit))
            conn.commit()
            conn.close()
            st.success("✅ Material agregado al inventario.")
            st.rerun()

    conn = get_connection()
    df_inv = pd.read_sql_query("SELECT * FROM inventario_materiales ORDER BY id DESC", conn)
    conn.close()
    
    st.subheader("📋 Stock Actual en Almacén")
    st.dataframe(df_inv, use_container_width=True)

    if not df_inv.empty:
        with st.expander("🗑️ Descontar / Borrar Ítem del Inventario"):
            op_inv = {f"ID #{r['id']} | {r['nombre_marca']} ({r['color_descripcion']}) - Stock: {r['stock_cantidad']} {r['unidad']}": r['id'] for _, r in df_inv.iterrows()}
            sel_inv = st.selectbox("Selecciona ítem a gestionar:", list(op_inv.keys()))
            if st.button("🚨 Eliminar / Descartar Ítem", type="primary"):
                conn = get_connection()
                conn.execute("DELETE FROM inventario_materiales WHERE id = ?", (op_inv[sel_inv],))
                conn.commit()
                conn.close()
                st.success("✅ Ítem eliminado del inventario.")
                st.rerun()

elif modulo == "🧮 5. Cotizador 3D (Múltiples Ítems)":
    st.header("🧮 Calculadora de Costos Impresión 3D (Múltiples Ítems Protofab)")
    
    if "items_cotizacion" not in st.session_state:
        st.session_state["items_cotizacion"] = []

    if "codigo_oferta_actual" not in st.session_state:
        st.session_state["codigo_oferta_actual"] = f"COT-{date.today().strftime('%Y%m%d')}-01"

    st.subheader("🛠️ 1. Agregar Ítem a la Cotización")
    col_param1, col_param2, col_param3, col_param4, col_param5, col_param6 = st.columns(6)
    
    costo_promedio_hora = col_param1.number_input("Costo x Hora (USD)", value=2.40, step=0.10, key="ct_hora")
    tiempo_h = col_param2.number_input("Tiempo (H)", value=0, min_value=0, step=1, key="ct_h")
    tiempo_m = col_param3.number_input("Tiempo (M)", value=45, min_value=0, max_value=59, step=1, key="ct_m")
    costo_material = col_param4.number_input("Costo Material ($)", value=0.72, step=0.01, key="ct_mat")
    multi_material_pct = col_param5.number_input("Multiplicador Material %", value=10.0, step=1.0, key="ct_mult")
    cantidad = col_param6.number_input("Cantidad", value=1, min_value=1, step=1, key="ct_cant")

    c_desc, c_add = st.columns([4, 1])
    desc_item = c_desc.text_input("Descripción del Servicio / Pieza", value="Impresión 3D de pieza personalizada bajo demanda", key="ct_desc")
    
    if c_add.button("➕ Agregar Ítem", use_container_width=True):
        desgaste_unitario = 0.00052
        tiempo_total_horas = tiempo_h + (tiempo_m / 60.0)
        
        costo_impresion_sin_material = costo_promedio_hora * tiempo_total_horas
        desgaste_maquina = desgaste_unitario * (tiempo_h * 60 + tiempo_m)
        ganancia_sobre_material = costo_material * (multi_material_pct / 100.0)
        material_total = costo_material + ganancia_sobre_material
        
        total_unitario = material_total + costo_impresion_sin_material + desgaste_maquina
        subtotal_item = total_unitario * cantidad
        
        st.session_state["items_cotizacion"].append({
            "cant": cantidad,
            "desc": desc_item,
            "pu": round(total_unitario, 2),
            "sub": round(subtotal_item, 2)
        })
        st.success("✅ Ítem agregado al presupuesto.")
        st.rerun()

    st.divider()
    st.subheader("📋 2. Presupuesto Actual")
    
    if st.session_state["items_cotizacion"]:
        for index, item in enumerate(st.session_state["items_cotizacion"]):
            col_cant, col_desc, col_pu, col_sub, col_del = st.columns([1, 4, 1.2, 1.2, 0.8])
            
            nueva_cant = col_cant.number_input("Cant.", value=item["cant"], min_value=1, key=f"cant_{index}")
            nueva_desc = col_desc.text_input("Descripción", value=item["desc"], key=f"desc_{index}")
            
            if nueva_cant != item["cant"] or nueva_desc != item["desc"]:
                st.session_state["items_cotizacion"][index]["cant"] = nueva_cant
                st.session_state["items_cotizacion"][index]["desc"] = nueva_desc
                st.session_state["items_cotizacion"][index]["sub"] = round(item["pu"] * nueva_cant, 2)
                st.rerun()

            col_pu.markdown(f"<p style='margin-top:35px;'><b>PU:</b> ${item['pu']:,.2f} USD</p>", unsafe_allow_html=True)
            col_sub.markdown(f"<p style='margin-top:35px;'><b>Subtotal:</b> ${item['sub']:,.2f} USD</p>", unsafe_allow_html=True)
            
            if col_del.button("🗑️", key=f"del_{index}", help="Eliminar este ítem"):
                st.session_state["items_cotizacion"].pop(index)
                st.success("Ítem removido")
                st.rerun()
                
        subtotal_global = sum(item["sub"] for item in st.session_state["items_cotizacion"])
        
        iva_pct = st.number_input("IVA aplicable (%)", value=16.0, step=1.0)
        facturable_of = st.checkbox("Incluir Factura Fiscal (+ IVA)", value=True)
        
        iva_global = subtotal_global * (iva_pct / 100.0) if facturable_of else 0.0
        total_global = subtotal_global + iva_global

        col_tot1, col_tot2, col_tot3 = st.columns(3)
        col_tot1.metric("Subtotal Sin IVA", f"${subtotal_global:,.2f} USD")
        col_tot2.metric(f"IVA ({iva_pct}%)", f"${iva_global:,.2f} USD" if facturable_of else "$0.00 USD")
        col_tot3.metric("TOTAL DE LA OFERTA", f"${total_global:,.2f} USD")

        if st.button("🧹 Vaciar Presupuesto completo"):
            st.session_state["items_cotizacion"] = []
            st.rerun()

        st.divider()
        st.subheader("📄 3. Datos de la Oferta para el Cliente")
        
        c_cod, c_cli, c_rif = st.columns(3)
        codigo_oferta = c_cod.text_input("Código de Cotización", value=st.session_state["codigo_oferta_actual"])
        st.session_state["codigo_oferta_actual"] = codigo_oferta
        
        cliente_of = c_cli.text_input("Nombre del Cliente / Empresa", value="Cliente Protofab")
        rif_of = c_rif.text_input("RIF / Cédula del Cliente", value="J-00000000-0")
        
        c_tel, c_serv = st.columns(2)
        tel_of = c_tel.text_input("Teléfono de Contacto", value="+58 414-0000000")
        cat_of = c_serv.selectbox("Servicio", ["Impresión 3D bajo demanda", "Diseño e impresión 3D", "Proyecto especial"])

        datos_pdf = {
            "codigo": codigo_oferta,
            "fecha": str(date.today()),
            "cliente": cliente_of,
            "rif": rif_of,
            "telefono": tel_of,
            "categoria": cat_of,
            "items": st.session_state["items_cotizacion"],
            "subtotal_usd": subtotal_global,
            "es_facturable": facturable_of,
            "iva_pct": iva_pct,
            "iva_usd": iva_global,
            "total_usd": total_global
        }
        
        pdf_bytes = generar_pdf_cotizacion_usd(datos_pdf)
        
        st.download_button(
            label="⬇️ Descargar Cotización PDF Oficial (Solo USD)",
            data=pdf_bytes,
            file_name=f"{codigo_oferta}_{cliente_of.replace(' ', '_')}.pdf",
            mime="application/pdf",
            type="primary"
        )
    else:
        st.info("⚠️ Agrega al menos un ítem al presupuesto para desplegar la sección del cliente y la opción de descarga del PDF.")

# ==============================================================================
# 6. DEUDAS (CxC / CxP) CON FUNCIÓN DE SALDAR / ABONAR
# ==============================================================================
elif modulo == "📋 6. Deudas (CxC / CxP)":
    st.header("📋 Cuentas por Cobrar (Clientes) y Cuentas por Pagar (Proveedores/Socios)")
    
    with st.form("form_deuda"):
        c1, c2, c3, c4 = st.columns(4)
        tipo_d = c1.selectbox("Tipo", ["Por Cobrar (Cliente)", "Por Pagar (Proveedor/Socio)"])
        contraparte = c2.text_input("Contraparte")
        fecha_venc = c3.date_input("Vencimiento", value=date.today())
        concepto_d = c4.text_input("Concepto")

        c5, c6 = st.columns(2)
        monto_tot = c5.number_input("Monto Total ($)", min_value=0.0, step=5.0)
        monto_abo = c6.number_input("Abono Inicial ($)", min_value=0.0, step=5.0)

        if st.form_submit_button("💾 Registrar Deuda") and monto_tot > 0:
            saldo = max(0.0, monto_tot - monto_abo)
            estado_d = "Pagada" if saldo == 0 else ("Abono Parcial" if monto_abo > 0 else "Pendiente")
            conn = get_connection()
            conn.execute("INSERT INTO deudas (fecha_registro, fecha_vencimiento, tipo, contraparte, concepto, monto_total_usd, monto_abonado_usd, saldo_pendiente_usd, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (str(date.today()), str(fecha_venc), tipo_d, contraparte, concepto_d, monto_tot, monto_abo, saldo, estado_d))
            conn.commit()
            conn.close()
            st.success("✅ Deuda guardada correctamente.")
            st.rerun()

    conn = get_connection()
    df_d = pd.read_sql_query("SELECT * FROM deudas ORDER BY id DESC", conn)
    conn.close()
    
    st.subheader("📋 Cartera de Deudas Actual")
    st.dataframe(df_d, use_container_width=True)

    if not df_d.empty:
        st.divider()
        st.subheader("💵 Registrar Abono o Saldar Deuda Existente")
        with st.form("form_saldar"):
            op_deudas = {f"ID #{r['id']} | [{r['tipo']}] {r['contraparte']} - Pendiente: ${r['saldo_pendiente_usd']:,.2f} USD ({r['concepto']})": r['id'] for _, r in df_d.iterrows() if r['saldo_pendiente_usd'] > 0}
            
            if op_deudas:
                sel_deuda_key = st.selectbox("Selecciona la deuda a abonar/saldar:", list(op_deudas.keys()))
                id_a_saldar = op_deudas[sel_deuda_key]
                
                # Buscar el saldo actual de ese ID
                deuda_actual = df_d[df_d['id'] == id_a_saldar].iloc[0]
                saldo_actual = deuda_actual['saldo_pendiente_usd']
                
                monto_abono_nuevo = st.number_input("Monto del Abono / Pago a realizar ($)", min_value=0.0, max_value=float(saldo_actual), value=float(saldo_actual), step=1.0)
                
                if st.form_submit_button("✅ Aplicar Abono / Saldar Deuda"):
                    nuevo_abonado = deuda_actual['monto_abonado_usd'] + monto_abono_nuevo
                    nuevo_saldo = max(0.0, deuda_actual['monto_total_usd'] - nuevo_abonado)
                    nuevo_estado = "Pagada" if nuevo_saldo == 0 else "Abono Parcial"
                    
                    conn = get_connection()
                    conn.execute("UPDATE deudas SET monto_abonado_usd = ?, saldo_pendiente_usd = ?, estado = ? WHERE id = ?",
                                 (nuevo_abonado, nuevo_saldo, nuevo_estado, id_a_saldar))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ ¡Deuda actualizada con éxito! Nuevo saldo pendiente: ${nuevo_saldo:,.2f} USD")
                    st.rerun()
            else:
                st.info("No hay deudas pendientes por cobrar o pagar en este momento.")

        with st.expander("🗑️ Eliminar Registro de Deuda"):
            op_del = {f"ID #{r['id']} | {r['contraparte']} - ${r['saldo_pendiente_usd']:,.2f}": r['id'] for _, r in df_d.iterrows()}
            sel_del = st.selectbox("Seleccionar deuda a eliminar:", list(op_del.keys()))
            if st.button("🚨 Eliminar Registro", type="primary"):
                conn = get_connection()
                conn.execute("DELETE FROM deudas WHERE id = ?", (op_del[sel_del],))
                conn.commit()
                conn.close()
                st.success("✅ Registro de deuda eliminado.")
                st.rerun()

# ==============================================================================
# 7. TASAS BCV & LIMPIEZA
# ==============================================================================
elif modulo == "🏦 7. Tasas BCV & Limpieza":
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

    conn = get_connection()
    st.dataframe(pd.read_sql_query("SELECT * FROM tasas_bcv ORDER BY fecha DESC", conn), use_container_width=True)

    st.divider()
    if st.button("🗑️ Vaciar Todos los Registros Operativos"):
        conn = get_connection()
        conn.execute("DELETE FROM ingresos")
        conn.execute("DELETE FROM egresos")
        conn.execute("DELETE FROM inventario_materiales")
        conn.execute("DELETE FROM deudas")
        conn.commit()
        conn.close()
        st.success("✅ Sistema limpiado.")
        st.rerun()