-- ============================================================================
-- PROTOFAB ERP & FINANZAS BIMONETARIO (USD BCV / VES)
-- Esquema de Base de Datos Relacional para PostgreSQL / Supabase
-- ============================================================================

-- 1. Tabla de Tasas Históricas BCV
CREATE TABLE IF NOT EXISTS tasas_bcv (
    id SERIAL PRIMARY KEY,
    fecha DATE UNIQUE NOT NULL,
    tasa_bcv NUMERIC(12,4) NOT NULL,
    tasa_paralelo NUMERIC(12,4) DEFAULT 0.0,
    notas TEXT
);

-- 2. Catálogo de Impresoras 3D
CREATE TABLE IF NOT EXISTS impresoras (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    consumo_watts REAL NOT NULL,
    costo_hora_usd REAL DEFAULT 2.40,
    desgaste_por_hora REAL DEFAULT 0.00052,
    activa INTEGER DEFAULT 1
);

-- 3. Catálogo de Materiales / Filamentos
CREATE TABLE IF NOT EXISTS materiales (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    costo_kg_usd REAL NOT NULL,
    stock_gramos REAL DEFAULT 1000.0
);

-- 4. Tabla de Ingresos (Ventas y Servicios)
CREATE TABLE IF NOT EXISTS ingresos (
    id SERIAL PRIMARY KEY,
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
);

-- 5. Tabla de Egresos (Costos y Gastos Operativos)
CREATE TABLE IF NOT EXISTS egresos (
    id SERIAL PRIMARY KEY,
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
);

-- 6. Tabla de Ofertas / Cotizaciones
CREATE TABLE IF NOT EXISTS ofertas (
    id SERIAL PRIMARY KEY,
    codigo_oferta TEXT UNIQUE NOT NULL,
    fecha_emision DATE NOT NULL,
    cliente TEXT NOT NULL,
    rif_cedula TEXT,
    telefono TEXT,
    categoria_servicio TEXT NOT NULL,
    descripcion_items TEXT NOT NULL,
    impresora_usada TEXT,
    material_usado TEXT,
    peso_gramos REAL DEFAULT 0.0,
    tiempo_impresion_horas REAL DEFAULT 0.0,
    horas_diseno REAL DEFAULT 0.0,
    costo_interno_usd REAL DEFAULT 0.0,
    es_facturable INTEGER DEFAULT 0,
    subtotal_usd REAL NOT NULL,
    iva_usd REAL NOT NULL,
    total_usd REAL NOT NULL,
    tasa_bcv_referencia REAL NOT NULL,
    total_ves REAL NOT NULL,
    estado TEXT DEFAULT 'Enviada'
);

-- 7. Tabla de Deudas (CxC y CxP)
CREATE TABLE IF NOT EXISTS deudas (
    id SERIAL PRIMARY KEY,
    fecha_registro DATE NOT NULL,
    fecha_vencimiento DATE,
    tipo TEXT NOT NULL,
    contraparte TEXT NOT NULL,
    concepto TEXT NOT NULL,
    monto_total_usd REAL NOT NULL,
    monto_abonado_usd REAL DEFAULT 0.0,
    saldo_pendiente_usd REAL NOT NULL,
    estado TEXT DEFAULT 'Pendiente'
);