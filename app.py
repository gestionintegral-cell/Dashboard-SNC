import pandas as pd
import plotly.express as px
import streamlit as st

# Configuración de interfaz
st.set_page_config(
    page_title="Sistema de Control de Salidas No Conformes",
    page_icon="📈",
    layout="wide",
)

# Estilo personalizado para tarjetas y títulos
st.markdown(
    """
    <style>
    .main-title {
        font-size: 26px;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 4px;
    }
    .sub-title {
        font-size: 14px;
        color: #64748B;
        margin-bottom: 24px;
    }
    .metric-box {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 12px 16px;
        text-align: left;
    }
    .metric-label {
        font-size: 12px;
        color: #64748B;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-num {
        font-size: 22px;
        color: #0F172A;
        font-weight: 700;
        margin-top: 4px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Encabezado corporativo
st.markdown(
    '<div class="main-title">Control de Salidas No Conformes (SNC)</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="sub-title">Monitoreo y seguimiento al Sistema de Gestión de la Calidad</div>',
    unsafe_allow_html=True,
)


# Carga de datos
@st.cache_data(ttl=60)
def cargar_base_datos():
    url = "https://docs.google.com/spreadsheets/d/1N9So7ddadDxy2TPhpZZUsnqlLUn6my-FvByFg3dOYf0/export?format=xlsx"
    xls = pd.ExcelFile(url)
    registros = []

    for hoja in xls.sheet_names:
        df_hoja = pd.read_excel(xls, sheet_name=hoja)
        df_hoja["Servicio"] = hoja
        registros.append(df_hoja)

    df_total = pd.concat(registros, ignore_index=True)

    # Identificación de fecha
    col_fecha = [
        c
        for c in df_total.columns
        if "fecha" in c.lower() and "identificaci" in c.lower()
    ]
    if col_fecha:
        df_total["Fecha_DT"] = pd.to_datetime(
            df_total[col_fecha[0]], errors="coerce"
        )
        df_total["Periodo"] = df_total["Fecha_DT"].dt.to_period("M")

    return df_total


try:
    df = cargar_base_datos()
except Exception as e:
    st.error(f"No fue posible cargar la base de datos de Google Sheets: {e}")
    st.stop()

# Mapeo de columnas
col_sede = [c for c in df.columns if c.upper() == "SEDE"]
col_estado = [
    c for c in df.columns if "estado" in c.lower() or "cerrad" in c.lower()
]
col_coyuntural = [
    c for c in df.columns if "coyuntural" in c.lower() and "Nº" not in c
]
col_incidente = [c for c in df.columns if "incidente" in c.lower()]
col_proceso = [
    c for c in df.columns if "proceso" in c.lower() or "área" in c.lower()
]
col_colaborador = [c for c in df.columns if "colaborador" in c.lower()]
col_momento = [c for c in df.columns if "momento" in c.lower()]
col_desc = [
    c for c in df.columns if "descripci" in c.lower() and "snc" in c.lower()
]

# Filtros laterales
st.sidebar.markdown("### Filtros de consulta")
sedes_disponibles = list(df[col_sede[0]].dropna().unique()) if col_sede else []
servicios_disponibles = list(df["Servicio"].dropna().unique())

sedes_seleccionadas = st.sidebar.multiselect(
    "Sede", sedes_disponibles, default=sedes_disponibles
)
servicios_seleccionados = st.sidebar.multiselect(
    "Servicio / Área", servicios_disponibles, default=servicios_disponibles
)

# Aplicación de filtros
df_f = df.copy()
if sedes_seleccionadas and col_sede:
    df_f = df_f[df_f[col_sede[0]].isin(sedes_seleccionadas)]
if servicios_seleccionados:
    df_f = df_f[df_f["Servicio"].isin(servicios_seleccionados)]

# Cálculo de variables principales
total_eventos = len(df_f)
cerrados = (
    len(df_f[df_f[col_estado[0]].astype(str).str.upper() == "SÍ"])
    if col_estado
    else 0
)
pendientes = total_eventos - cerrados
coyunturales = (
    len(df_f[df_f[col_coyuntural[0]].astype(str).str.upper() == "SÍ"])
    if col_coyuntural
    else 0
)
incidentes = (
    len(df_f[df_f[col_incidente[0]].astype(str).str.upper() == "SÍ"])
    if col_incidente
    else 0
)
tasa_cierre = (cerrados / total_eventos * 100) if total_eventos > 0 else 0.0

# Fila de métricas clave
m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    st.markdown(
        f'<div class="metric-box"><div class="metric-label">Total SNC</div><div class="metric-num">{total_eventos}</div></div>',
        unsafe_allow_html=True,
    )
with m2:
    st.markdown(
        f'<div class="metric-box"><div class="metric-label">Efectividad de Cierre</div><div class="metric-num">{tasa_cierre:.1f}%</div></div>',
        unsafe_allow_html=True,
    )
with m3:
    st.markdown(
        f'<div class="metric-box"><div class="metric-label">Casos Pendientes</div><div class="metric-num">{pendientes}</div></div>',
        unsafe_allow_html=True,
    )
with m4:
    st.markdown(
        f'<div class="metric-box"><div class="metric-label">Acción Coyuntural</div><div class="metric-num">{coyunturales}</div></div>',
        unsafe_allow_html=True,
    )
with m5:
    st.markdown(
        f'<div class="metric-box"><div class="metric-label">Incidentes</div><div class="metric-num">{incidentes}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# Segmentación rápida
segmento = st.radio(
    "Filtrar vista por estado del registro:",
    [
        "Todos los registros",
        "Pendientes",
        "Cerrados",
        "Con acción coyuntural",
        "Incidentes",
    ],
    horizontal=True,
)

if segmento == "Pendientes" and col_estado:
    df_v = df_f[df_f[col_estado[0]].astype(str).str.upper() != "SÍ"]
elif segmento == "Cerrados" and col_estado:
    df_v = df_f[df_f[col_estado[0]].astype(str).str.upper() == "SÍ"]
elif segmento == "Con acción coyuntural" and col_coyuntural:
    df_v = df_f[df_f[col_coyuntural[0]].astype(str).str.upper() == "SÍ"]
elif segmento == "Incidentes" and col_incidente:
    df_v = df_f[df_f[col_incidente[0]].astype(str).str.upper() == "SÍ"]
else:
    df_v = df_f.copy()

st.markdown("<hr style='margin:15px 0;'>", unsafe_allow_html=True)

# Pestañas analíticas
t_procesos, t_tiempo, t_personas, t_tabla = st.tabs(
    [
        "Análisis de Procesos y Fallas",
        "Evolución Temporal",
        "Gestión por Personal",
        "Registro Detallado",
    ]
)

# PESTAÑA 1: DESGLOSE DE PROCESOS Y INCIDENCIAS
with t_procesos:
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("##### Desglose de Incidencias por Servicio y Proceso")

        # Selector interactivamente focalizado
        servicio_focal = st.selectbox(
            "Seleccionar servicio para analizar sus procesos internos:",
            options=["Todos los servicios"]
            + list(df_v["Servicio"].unique()),
        )

        if servicio_focal != "Todos los servicios":
            df_proc_view = df_v[df_v["Servicio"] == servicio_focal]
        else:
            df_proc_view = df_v.copy()

        if col_proceso:
            df_p = (
                df_proc_view[col_proceso[0]]
                .value_counts()
                .reset_index()
                .head(10)
            )
            df_p.columns = ["Proceso / Área", "Eventos"]

            fig_p = px.bar(
                df_p,
                x="Eventos",
                y="Proceso / Área",
                orientation="h",
                color="Eventos",
                color_continuous_scale="Blues",
            )
            fig_p.update_layout(
                yaxis={"categoryorder": "total ascending"},
                margin=dict(l=0, r=20, t=20, b=20),
            )
            st.plotly_chart(fig_p, use_container_width=True)

    with col_right:
        st.markdown("##### Principales Causas / Descripciones Reportadas")
        if col_desc:
            df_d = (
                df_v[col_desc[0]].value_counts().reset_index().head(8)
            )
            df_d.columns = ["Causa / Descripción", "Frecuencia"]

            fig_d = px.bar(
                df_d,
                x="Frecuencia",
                y="Causa / Descripción",
                orientation="h",
                color="Frecuencia",
                color_continuous_scale="Slategreen",
            )
            fig_d.update_layout(
                yaxis={"categoryorder": "total ascending"},
                margin=dict(l=0, r=20, t=20, b=20),
            )
            st.plotly_chart(fig_d, use_container_width=True)

    st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)

    if col_momento:
        st.markdown("##### Detección del Evento según la Etapa del Servicio")
        fig_m = px.histogram(
            df_v,
            x="Servicio",
            color=col_momento[0],
            barmode="group",
            color_discrete_sequence=px.colors.qualitative.Slate,
        )
        fig_m.update_layout(margin=dict(l=0, r=0, t=20, b=20))
        st.plotly_chart(fig_m, use_container_width=True)

# PESTAÑA 2: EVOLUCIÓN TEMPORAL
with t_tiempo:
    st.markdown("##### Comportamiento Mensual de Registros")
    if "Periodo" in df_v.columns and not df_v["Periodo"].dropna().empty:
        df_t = df_v.groupby("Periodo").size().reset_index(name="Frecuencia")
        df_t["Periodo"] = df_t["Periodo"].astype(str)

        fig_t = px.line(
            df_t,
            x="Periodo",
            y="Frecuencia",
            markers=True,
            line_shape="linear",
        )
        fig_t.update_traces(line_color="#1E293B", line_width=2)
        fig_t.update_layout(margin=dict(l=0, r=0, t=20, b=20))
        st.plotly_chart(fig_t, use_container_width=True)
    else:
        st.info(
            "Se consolidará el gráfico temporal a medida que se ingresen fechas en la columna correspondiente."
        )

# PESTAÑA 3: GESTIÓN POR PERSONAL
with t_personas:
    p_col1, p_col2 = st.columns(2)

    with p_col1:
        st.markdown("##### Frecuencia de Eventos por Colaborador")
        if col_colaborador:
            df_c = (
                df_v[col_colaborador[0]]
                .value_counts()
                .reset_index()
                .head(10)
            )
            df_c.columns = ["Nombre Colaborador", "Registros"]
            st.dataframe(df_c, use_container_width=True)

    with p_col2:
        st.markdown("##### Participación por Servicio")
        fig_s = px.pie(
            df_v,
            names="Servicio",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        fig_s.update_layout(margin=dict(l=0, r=0, t=20, b=20))
        st.plotly_chart(fig_s, use_container_width=True)

# PESTAÑA 4: REGISTRO COMPLETO Y DESCARGA
with t_tabla:
    st.markdown(f"##### Tabla de Datos - Vista Actual ({segmento})")

    csv = df_v.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Exportar vista actual a CSV",
        data=csv,
        file_name="reporte_snc.csv",
        mime="text/csv",
    )

    st.dataframe(df_v, use_container_width=True)
