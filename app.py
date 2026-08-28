import pandas as pd
import plotly.express as px
import streamlit as st

# 1. Configuración general del panel
st.set_page_config(
    page_title="Dashboard de Salidas No Conformes (SNC)",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Panel de Control - Salidas No Conformes (SNC)")
st.markdown(
    "Monitoreo analítico e interactivo en tiempo real del Sistema de Gestión de Calidad."
)


# 2. Conexión y consolidación automática de Google Sheets
@st.cache_data(ttl=60)
def cargar_datos_google_sheets():
    # Enlace de exportación Excel de tu Google Sheets
    url_google_sheets = "https://docs.google.com/spreadsheets/d/1N9So7ddadDxy2TPhpZZUsnqlLUn6my-FvByFg3dOYf0/export?format=xlsx"

    xls = pd.ExcelFile(url_google_sheets)
    lista_dfs = []

    for nombre_hoja in xls.sheet_names:
        df_hoja = pd.read_excel(xls, sheet_name=nombre_hoja)
        df_hoja["Servicio"] = nombre_hoja
        lista_dfs.append(df_hoja)

    df_consolidado = pd.concat(lista_dfs, ignore_index=True)

    # Convertir columna de fecha
    col_fecha = [
        c
        for c in df_consolidado.columns
        if "fecha" in c.lower() and "identificaci" in c.lower()
    ]
    if col_fecha:
        df_consolidado["Fecha_DT"] = pd.to_datetime(
            df_consolidado[col_fecha[0]], errors="coerce"
        )
        df_consolidado["Año_Mes"] = df_consolidado["Fecha_DT"].dt.to_period("M")

    return df_consolidado


try:
    df_raw = cargar_datos_google_sheets()
except Exception as e:
    st.error(f"⚠️ Error al conectar con Google Sheets: {e}")
    st.stop()

# 3. Mapeo inteligente de columnas clave
col_sede = [c for c in df_raw.columns if c.upper() == "SEDE"]
col_estado = [
    c for c in df_raw.columns if "estado" in c.lower() or "cerrad" in c.lower()
]
col_coyuntural = [
    c for c in df_raw.columns if "coyuntural" in c.lower() and "Nº" not in c
]
col_incidente = [c for c in df_raw.columns if "incidente" in c.lower()]
col_proceso = [
    c for c in df_raw.columns if "proceso" in c.lower() or "área" in c.lower()
]
col_colaborador = [c for c in df_raw.columns if "colaborador" in c.lower()]
col_momento = [c for c in df_raw.columns if "momento" in c.lower()]
col_descripcion = [
    c for c in df_raw.columns if "descripci" in c.lower() and "snc" in c.lower()
]

# 4. Barra Lateral de Filtros Globales
st.sidebar.header("🔍 Filtros Globales")

sedes_disp = (
    list(df_raw[col_sede[0]].dropna().unique()) if col_sede else []
)
servicios_disp = list(df_raw["Servicio"].dropna().unique())

sedes_sel = st.sidebar.multiselect("Sede:", sedes_disp, default=sedes_disp)
servicios_sel = st.sidebar.multiselect(
    "Servicio:", servicios_disp, default=servicios_disp
)

# Aplicar filtros
df_filtrado = df_raw.copy()
if sedes_sel and col_sede:
    df_filtrado = df_filtrado[df_filtrado[col_sede[0]].isin(sedes_sel)]
if servicios_sel:
    df_filtrado = df_filtrado[df_filtrado["Servicio"].isin(servicios_sel)]

# 5. Cálculo de Indicadores (KPIs)
total_snc = len(df_filtrado)
cerradas = (
    len(df_filtrado[df_filtrado[col_estado[0]].astype(str).str.upper() == "SÍ"])
    if col_estado
    else 0
)
abiertas = total_snc - cerradas
coyunturales = (
    len(
        df_filtrado[
            df_filtrado[col_coyuntural[0]].astype(str).str.upper() == "SÍ"
        ]
    )
    if col_coyuntural
    else 0
)
incidentes = (
    len(
        df_filtrado[
            df_filtrado[col_incidente[0]].astype(str).str.upper() == "SÍ"
        ]
    )
    if col_incidente
    else 0
)
pct_cierre = (cerradas / total_snc * 100) if total_snc > 0 else 0.0

# Despliegue de métricas
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total SNC", total_snc)
c2.metric("% Cierre", f"{pct_cierre:.1f}%")
c3.metric("Pendientes", abiertas)
c4.metric("Acc. Coyuntural", coyunturales)
c5.metric("Incidentes", incidentes)

st.divider()

# 6. Selector de Interacción Rápida
st.subheader("⚡ Filtrado Interactivo por Estado")
categoria_sel = st.radio(
    "Selecciona un segmento para enfocar los gráficos y tablas:",
    [
        "Todas las SNC",
        "Pendientes (Abiertas)",
        "Cerradas",
        "Requieren Acción Coyuntural",
        "Es Incidente",
    ],
    horizontal=True,
)

if categoria_sel == "Pendientes (Abiertas)" and col_estado:
    df_vista = df_filtrado[
        df_filtrado[col_estado[0]].astype(str).str.upper() != "SÍ"
    ]
elif categoria_sel == "Cerradas" and col_estado:
    df_vista = df_filtrado[
        df_filtrado[col_estado[0]].astype(str).str.upper() == "SÍ"
    ]
elif categoria_sel == "Requieren Acción Coyuntural" and col_coyuntural:
    df_vista = df_filtrado[
        df_filtrado[col_coyuntural[0]].astype(str).str.upper() == "SÍ"
    ]
elif categoria_sel == "Es Incidente" and col_incidente:
    df_vista = df_filtrado[
        df_filtrado[col_incidente[0]].astype(str).str.upper() == "SÍ"
    ]
else:
    df_vista = df_filtrado.copy()

# 7. Estranquización por Pestañas Estratégicas
tab_tendencia, tab_causas, tab_personas, tab_tabla = st.tabs(
    [
        "📈 Tendencia Temporal",
        "🎯 Causa Raíz (Pareto) & Momentos",
        "👥 Análisis por Personal",
        "📋 Registro Detallado",
    ]
)

# PESTAÑA 1: EVOLUCIÓN MENSUAL
with tab_tendencia:
    st.subheader("📆 Comportamiento de SNC a lo Largo del Tiempo")
    if "Año_Mes" in df_vista.columns and not df_vista["Año_Mes"].dropna().empty:
        df_temp = (
            df_vista.groupby("Año_Mes").size().reset_index(name="Cantidad")
        )
        df_temp["Año_Mes"] = df_temp["Año_Mes"].astype(str)

        fig_linea = px.line(
            df_temp,
            x="Año_Mes",
            y="Cantidad",
            markers=True,
            title="Evolución Mensual de Registros",
            labels={"Año_Mes": "Mes", "Cantidad": "Número de SNC"},
        )
        st.plotly_chart(fig_linea, use_container_width=True)
    else:
        st.info(
            "Se mostrará el gráfico de tendencia una vez ingreses fechas válidas en la columna 'Fecha Identificación'."
        )

# PESTAÑA 2: PARETO Y MOMENTOS DE DETECCIÓN
with tab_causas:
    g1, g2 = st.columns(2)

    with g1:
        st.subheader("📌 Pareto: Principales Descripciones de Fallas")
        col_desc = (
            col_descripcion[0]
            if col_descripcion
            else (col_proceso[0] if col_proceso else None)
        )
        if col_desc:
            df_top_desc = (
                df_vista[col_desc].value_counts().reset_index().head(10)
            )
            df_top_desc.columns = ["Falla / Descripción", "Frecuencia"]
            fig_p = px.bar(
                df_top_desc,
                x="Frecuencia",
                y="Falla / Descripción",
                orientation="h",
                color="Frecuencia",
                color_continuous_scale="Reds",
                title="Top 10 Fallas más Recurrentes",
            )
            fig_p.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig_p, use_container_width=True)

    with g2:
        st.subheader("🛡️ Oportunidad de Detección (Fase/Momento)")
        if col_momento:
            fig_m = px.histogram(
                df_vista,
                x="Servicio",
                color=col_momento[0],
                barmode="group",
                title="Detección: Antes vs. Durante vs. Después del Servicio",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            st.plotly_chart(fig_m, use_container_width=True)

# PESTAÑA 3: ANÁLISIS POR PERSONAL
with tab_personas:
    p1, p2 = st.columns(2)

    with p1:
        st.subheader("🚨 Colaboradores con Mayor Número de Reportes")
        if col_colaborador:
            df_col = (
                df_vista[col_colaborador[0]]
                .value_counts()
                .reset_index()
                .head(10)
            )
            df_col.columns = ["Colaborador", "Total Registros"]
            st.dataframe(df_col, use_container_width=True)
        else:
            st.info("No se encontró la columna de colaborador.")

    with p2:
        st.subheader("🏢 Proporción por Área / Servicio")
        fig_serv = px.pie(
            df_vista,
            names="Servicio",
            title="Distribución Porcentual",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        st.plotly_chart(fig_serv, use_container_width=True)

# PESTAÑA 4: TABLA DETALLADA CON DESCARGA
with tab_tabla:
    st.subheader(f"📋 Registros Filtrados ({categoria_sel})")

    # Botón para descargar a CSV directamente
    csv = df_vista.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Descargar datos filtrados en CSV",
        data=csv,
        file_name="reporte_snc_filtrado.csv",
        mime="text/csv",
    )

    st.dataframe(df_vista, use_container_width=True)
