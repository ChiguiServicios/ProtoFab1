# ⚙️ PROTOFAB ERP - Sistema Financiero Bimonetario y Cotizador 3D

## Guía de Despliegue Rápido (Para José y Jesús)

Este paquete contiene el **MVP funcional completo en Python** listo para ejecutarse tanto de forma **100% local** en cualquier PC del taller u oficina como **en línea (nube gratuita)** mediante Streamlit Cloud + Supabase (PostgreSQL).

### 1. Estructura del Proyecto
- `app.py`: Aplicación web completa (Dashboard directivo, Ingresos/Egresos bimonetarios con desglose de IVA 16%, Calculadora técnica de Impresión 3D/CAD con emisión de PDF al instante, Cartera CxC/CxP y Tasas BCV).
- `schema.sql`: Esquema relacional de las 7 tablas del sistema (compatible con SQLite para uso local inmediato y PostgreSQL/Supabase para nube).
- `requirements.txt`: Librerías necesarias (100% Open Source y gratuitas).

### 2. Cómo correrlo localmente hoy mismo (0$)
1. Instalar Python 3.10+ en la computadora.
2. Abrir la terminal en la carpeta `protofab_erp` y ejecutar:
   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```
3. Se abrirá automáticamente en el navegador en `http://localhost:8501` y creará el archivo de base de datos local `protofab_erp.db`.

### 3. Cómo conectarlo en línea gratis para todos los socios
1. Crear un proyecto gratuito en **Supabase.com** (PostgreSQL) y ejecutar el contenido de `schema.sql` en el *SQL Editor*.
2. Subir esta carpeta a un repositorio privado de **GitHub**.
3. Conectar el repositorio en **share.streamlit.io** (Streamlit Community Cloud) para obtener el enlace web privado de Protofab accesible desde iPhone, Android o PC.
