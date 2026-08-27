import pandas as pd
import plotly.express as px
import streamlit as st

# 1. Configuración de la página web
st.set_page_config(
    page_title="Dashboard Salidas No Conformes (SNC)",
    page_icon="📊",
    layout="wide",
)

# Estilos CSS
st.markdown(
    """
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border-left: 5px solid #1f77b4;
    }
    .metric-title { font-size: 13px; color: #6c757d; font-weight: bold; }
    .metric-value { font-size: 24px; color: #212529; font-weight: bold; margin-top: 5px; }
</style>
""",
    unsafe_allow_html=True,
)

st.title("📊 Panel de Control - Salidas No Conformes (SNC)")
st.markdown(
    "Monitoreo en tiempo real del Sistema de Gestión de Calidad por servicio y sede."
)


# 2. Conexión a Google Sheets
@st.cache_data(ttl=60)
def cargar_datos_google_sheets():
    # ID pública de tu Google Sheet
    SHEET_ID = "1N9So7ddadDxy2TPhpZZUsnqlLUn6my-FvByFg3dOYf0"
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"

    xls = pd.ExcelFile(url)
    lista_dfs = []

    # Se omiten pestañas que no son de diligenciamiento
    hojas_a_ignorar = ["Matriz_de_identificación_SNC"]

    for nombre_hoja in xls.sheet_names:
        if nombre_hoja not in hojas_a_ignorar:
            df_hoja = pd.read_excel(xls, sheet_name=nombre_hoja)
            df_hoja["Servicio"] = nombre_hoja.strip()
            lista_dfs.append(df_hoja)

    df_consolidado = pd.concat(lista_dfs, ignore_index=True)

    # Limpieza de fechas
    col_fecha = [
        c for c in df_consolidado.columns if "Fecha identificación" in c
    ]
    if col_fecha:
        df_consolidado["Fecha_Limpia"] = pd.to_datetime(
            df_consolidado[col_fecha[0]], errors="coerce"
        )

    return df_consolidado


try:
    df_raw = cargar_datos_google_sheets()
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

# 3. Mapeo de columnas según tu estructura
col_sede = "SEDE" if "SEDE" in df_raw.columns else None
col_estado = [c for c in df_raw.columns if "Estado" in c]
col_estado = col_estado[0] if col_estado else None
col_coyuntural = [c for c in df_raw.columns if "coyuntural" in c.lower()]
col_coyuntural = col_coyuntural[0] if col_coyuntural else None
col_incidente = [c for c in df_raw.columns if "incidente" in c.lower()]
col_incidente = col_incidente[0] if col_incidente else None
col_proceso = [c for c in df_raw.columns if "Proceso donde" in c]
col_proceso = col_proceso[0] if col_proceso else None

# 4. Filtros Laterales
st.sidebar.header("🔍 Filtros")
sedes = list(df_raw[col_sede].dropna().unique()) if col_sede else []
servicios = list(df_raw["Servicio"].dropna().unique())
estados = list(df_raw[col_estado].dropna().unique()) if col_estado else []

sedes_sel = st.sidebar.multiselect("Sede:", sedes, default=sedes)
servicios_sel = st.sidebar.multiselect(
    "Servicio / Área:", servicios, default=servicios
)
estados_sel = st.sidebar.multiselect("Estado:", estados, default=estados)

# Aplicación de Filtros
df_filtrado = df_raw.copy()
if sedes_sel and col_sede:
    df_filtrado = df_filtrado[df_filtrado[col_sede].isin(sedes_sel)]
if servicios_sel:
    df_filtrado = df_filtrado[df_filtrado["Servicio"].isin(servicios_sel)]
if estados_sel and col_estado:
    df_filtrado = df_filtrado[df_filtrado[col_estado].isin(estados_sel)]

# 5. Indicadores (KPIs)
total_snc = len(df_filtrado)
cerradas = (
    len(
        df_filtrado[
            df_filtrado[col_estado]
            .astype(str)
            .str.upper()
            .str.contains("CERRAD")
        ]
    )
    if col_estado
    else 0
)
abiertas = total_snc - cerradas
coyunturales = (
    len(
        df_filtrado[
            df_filtrado[col_coyuntural]
            .astype(str)
            .str.upper()
            .str.contains("SI|SÍ")
        ]
    )
    if col_coyuntural
    else 0
)
incidentes = (
    len(
        df_filtrado[
            df_filtrado[col_incidente]
            .astype(str)
            .str.upper()
            .str.contains("SI|SÍ")
        ]
    )
    if col_incidente
    else 0
)
pct_cierre = (cerradas / total_snc * 100) if total_snc > 0 else 0

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.markdown(
        f'<div class="metric-card"><div class="metric-title">TOTAL SNC</div><div class="metric-value">{total_snc}</div></div>',
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        f'<div class="metric-card" style="border-color:#2ca02c;"><div class="metric-title">% CERRADAS</div><div class="metric-value">{pct_cierre:.1f}%</div></div>',
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        f'<div class="metric-card" style="border-color:#d62728;"><div class="metric-title">PENDIENTES</div><div class="metric-value">{abiertas}</div></div>',
        unsafe_allow_html=True,
    )
with c4:
    st.markdown(
        f'<div class="metric-card" style="border-color:#ff7f0e;"><div class="metric-title">ACC. COYUNTURAL</div><div class="metric-value">{coyunturales}</div></div>',
        unsafe_allow_html=True,
    )
with c5:
    st.markdown(
        f'<div class="metric-card" style="border-color:#9467bd;"><div class="metric-title">INCIDENTES</div><div class="metric-value">{incidentes}</div></div>',
        unsafe_allow_html=True,
    )

st.divider()

# 6. Gráficos
c_graf1, c_graf2 = st.columns(2)

with c_graf1:
    st.subheader("📌 Salidas No Conformes por Servicio")
    if col_sede:
        fig1 = px.bar(
            df_filtrado,
            x="Servicio",
            color=col_sede,
            barmode="group",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        st.plotly_chart(fig1, use_container_width=True)

with c_graf2:
    st.subheader("🎯 Procesos con Mayor Frecuencia de Falla")
    if col_proceso:
        df_p = df_filtrado[col_proceso].value_counts().reset_index()
        df_p.columns = ["Proceso", "Cantidad"]
        fig2 = px.pie(
            df_p,
            values="Cantidad",
            names="Proceso",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        st.plotly_chart(fig2, use_container_width=True)

st.divider()

# 7. Tabla Interactiva
st.subheader("📋 Consolidado de Registros de Salidas No Conformes")
st.dataframe(df_filtrado, use_container_width=True)