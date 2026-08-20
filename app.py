import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from streamlit_option_menu import option_menu
from datetime import date

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
st.set_page_config(
    page_title="PURELECTRIC",
    page_icon=":sun:",
    layout="wide"
)

st.markdown(
    '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">',
    unsafe_allow_html=True
)

st.markdown("""
    <style>
    html, body, [class*="css"], .stApp, input, textarea, select, button {
        font-family: 'Segoe UI', sans-serif !important;
    }
    * {
        text-transform: uppercase !important;
    }
    </style>
""", unsafe_allow_html=True)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ============================================================
# CONEXIÓN A GOOGLE SHEETS
# ============================================================
@st.cache_resource
def get_client():
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)

@st.cache_resource
def get_spreadsheet():
    client = get_client()
    return client.open_by_key(st.secrets["spreadsheet_id"])

def get_worksheet(nombre_hoja: str, headers: list):
    sh = get_spreadsheet()
    try:
        ws = sh.worksheet(nombre_hoja)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=nombre_hoja, rows=1000, cols=len(headers))
        ws.append_row(headers)
    return ws

def leer_como_df(nombre_hoja: str, headers: list) -> pd.DataFrame:
    ws = get_worksheet(nombre_hoja, headers=headers)
    registros = ws.get_all_records()
    return pd.DataFrame(registros)

def agregar_fila(nombre_hoja: str, fila: list, headers: list):
    ws = get_worksheet(nombre_hoja, headers=headers)
    ws.append_row(fila)

# ============================================================
# HEADERS DE CADA HOJA
# ============================================================
HEADERS_MATERIALES = ["SKU", "Nombre", "Categoría", "Unidad", "Stock actual", "Stock mínimo", "Ubicación"]
HEADERS_PROYECTOS = ["Cliente", "Ubicación", "Tamaño (kW)", "Fecha estimada", "Estado", "Notas"]
ESTADOS_PROYECTO = ["Pendiente", "En proceso", "Completado"]

# ============================================================
# SIDEBAR - NAVEGACIÓN
# ============================================================
with st.sidebar:
    st.markdown("## PURELECTRIC")
    seccion = option_menu(
        menu_title=None,
        options=["Inicio", "Almacén", "Planeación"],
        icons=["house", "box-seam", "calendar3"],
        default_index=0,
    )

# ============================================================
# SECCIÓN: INICIO
# ============================================================
if seccion == "Inicio":
    st.title("PURELECTRIC")
    st.subheader("Sistema de Almacén y Planeación")
    st.markdown("""
    Bienvenido al sistema interno de PURELECTRIC.

    Utiliza el menú de la izquierda para navegar entre secciones:

    - **Almacén** — control de inventario de paneles, inversores, baterías, estructura y demás materiales.
    - **Planeación** — proyectos de instalación, requerimientos de material y estatus.

    Este sistema seguirá creciendo con más módulos conforme los vayamos definiendo.
    """)

# ============================================================
# SECCIÓN: ALMACÉN
# ============================================================
elif seccion == "Almacén":
    st.title("Almacén")

    tab_inventario, tab_agregar = st.tabs(["Inventario", "Agregar material"])

    with tab_inventario:
        df = leer_como_df("Materiales", headers=HEADERS_MATERIALES)

        if df.empty:
            st.info("Aún no hay materiales cargados. Agrega el primero en la pestaña 'Agregar material'.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                categorias = ["Todas"] + sorted(df["Categoría"].dropna().unique().tolist())
                filtro_cat = st.selectbox("Filtrar por categoría", categorias)
            with col2:
                busqueda = st.text_input("Buscar por nombre o SKU")

            df_filtrado = df.copy()
            if filtro_cat != "Todas":
                df_filtrado = df_filtrado[df_filtrado["Categoría"] == filtro_cat]
            if busqueda:
                mask = (
                    df_filtrado["Nombre"].str.contains(busqueda, case=False, na=False) |
                    df_filtrado["SKU"].astype(str).str.contains(busqueda, case=False, na=False)
                )
                df_filtrado = df_filtrado[mask]

            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

            try:
                bajo_stock = df_filtrado[
                    df_filtrado["Stock actual"].astype(float) <= df_filtrado["Stock mínimo"].astype(float)
                ]
                if not bajo_stock.empty:
                    st.warning(f"{len(bajo_stock)} material(es) por debajo del stock mínimo")
                    st.dataframe(bajo_stock, use_container_width=True, hide_index=True)
            except (ValueError, TypeError):
                pass

    with tab_agregar:
        st.subheader("Nuevo material")
        with st.form("form_nuevo_material", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                sku = st.text_input("SKU")
                nombre = st.text_input("Nombre")
                categoria = st.text_input("Categoría (ej. Panel, Inversor, Batería, Estructura, Cableado)")
            with c2:
                unidad = st.text_input("Unidad (pieza, metro, kit, etc.)")
                stock_actual = st.number_input("Stock actual", min_value=0.0, step=1.0)
                stock_minimo = st.number_input("Stock mínimo", min_value=0.0, step=1.0)
            ubicacion = st.text_input("Ubicación (ej. Bodega Central, En tránsito, Proyecto X)")

            enviado = st.form_submit_button("Guardar material")
            if enviado:
                if not sku or not nombre:
                    st.error("SKU y Nombre son obligatorios.")
                else:
                    agregar_fila(
                        "Materiales",
                        [sku.upper(), nombre.upper(), categoria.upper(), unidad.upper(),
                         stock_actual, stock_minimo, ubicacion.upper()],
                        headers=HEADERS_MATERIALES
                    )
                    st.success(f"Material '{nombre.upper()}' agregado correctamente.")
                    st.rerun()

# ============================================================
# SECCIÓN: PLANEACIÓN
# ============================================================
elif seccion == "Planeación":
    st.title("Planeación")

    tab_proyectos, tab_agregar = st.tabs(["Proyectos", "Agregar proyecto"])

    with tab_proyectos:
        df = leer_como_df("Proyectos", headers=HEADERS_PROYECTOS)

        if df.empty:
            st.info("Aún no hay proyectos cargados. Agrega el primero en la pestaña 'Agregar proyecto'.")
        else:
            filtro_estado = st.selectbox("Filtrar por estado", ["Todos"] + ESTADOS_PROYECTO)
            df_filtrado = df if filtro_estado == "Todos" else df[df["Estado"] == filtro_estado]
            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

    with tab_agregar:
        st.subheader("Nuevo proyecto")
        with st.form("form_nuevo_proyecto", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                cliente = st.text_input("Cliente")
                ubicacion = st.text_input("Ubicación")
                tamano_kw = st.number_input("Tamaño del sistema (kW)", min_value=0.0, step=0.5)
            with c2:
                fecha = st.date_input("Fecha estimada de instalación", value=date.today())
                estado = st.selectbox("Estado", ESTADOS_PROYECTO)
            notas = st.text_area("Notas")

            enviado = st.form_submit_button("Guardar proyecto")
            if enviado:
                if not cliente:
                    st.error("El nombre del cliente es obligatorio.")
                else:
                    agregar_fila(
                        "Proyectos",
                        [cliente.upper(), ubicacion.upper(), tamano_kw, str(fecha), estado, notas.upper()],
                        headers=HEADERS_PROYECTOS
                    )
                    st.success(f"Proyecto de '{cliente.upper()}' agregado correctamente.")
                    st.rerun()
