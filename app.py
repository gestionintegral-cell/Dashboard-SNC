import re
import pandas as pd
import streamlit as st
import google.generativeai as genai

# ---------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA STREAMLIT
# ---------------------------------------------------------
st.set_page_config(
    page_title="Dashboard SNC - COLMEDICOS",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Dashboard de Gestión de Calidad (SNC) - COLMEDICOS")

# ---------------------------------------------------------
# 2. CARGA DE DATOS DESDE GOOGLE SHEETS O EXCEL
# ---------------------------------------------------------
@st.cache_data(ttl=600)
def cargar_datos():
    # Sustituye con tu URL pública de Google Sheets en formato CSV o tu ruta local
    # Ejemplo de URL pública de Google Sheets:
    # url = "https://docs.google.com/spreadsheets/d/TU_ID/export?format=csv"
    
    # NOTA: Cambia esta ruta o URL por la fuente de tus datos
    url_o_ruta = "https://docs.google.com/spreadsheets/d/1N9So7ddadDxy2TPhpZZUsnqlLUn6my-FvByFg3dOYf0/edit?gid=935748465#gid=935748465" 
    
    try:
        df = pd.read_csv(url_o_ruta)
    except Exception:
        # Fallback a Excel si usas un archivo local .xlsx
        df = pd.read_excel("F-CAL-08 Control de salidas no conformes - SNC")
        
    return df

try:
    df_raw = cargar_datos()
except Exception as e:
    st.error(f"Error al cargar la base de datos: {e}")
    st.stop()

# Copia de trabajo
df = df_raw.copy()

# ---------------------------------------------------------
# 3. LIMPIEZA Y NORMALIZACIÓN DE DATOS (CORRECCIÓN ESTADO)
# ---------------------------------------------------------
# Normalizamos los nombres de las columnas quitando espacios iniciales/finales
df.columns = [c.strip() for c in df.columns]

# --- CORRECCIÓN CLAVE DE NOMBRES Y ESPACIOS EN ESTADO ---
if 'Estado' in df.columns:
    # Convertimos a texto, quitamos espacios invisibles antes/después y pasamos a mayúsculas
    df['Estado'] = df['Estado'].fillna('').astype(str).str.strip().str.upper()
else:
    st.error("La columna 'Estado' no fue encontrada en el archivo.")
    st.stop()

# Limpieza general de columnas de clasificación si existen
if 'Clasificacion' in df.columns:
    df['Clasificacion'] = df['Clasificacion'].fillna('').astype(str).str.strip().str.upper()

# Crear columna combinada para búsqueda rápida en el Chatbot
df['_search_text'] = df.apply(lambda row: ' '.join(row.values.astype(str)), axis=1)

# Identificar columna de colaborador/usuario si existe
col_colaborador = [c for c in df.columns if 'colaborador' in c.lower() or 'usuario' in c.lower()]

# ---------------------------------------------------------
# 4. FILTROS LATERALES (SIDEBAR)
# ---------------------------------------------------------
st.sidebar.header("🔍 Filtros de Datos")

# Filtro por Estado
estados_disponibles = list(df['Estado'].unique())
estado_seleccionado = st.sidebar.multiselect(
    "Filtrar por Estado:",
    options=estados_disponibles,
    default=estados_disponibles
)

# Aplicar filtro
if estado_seleccionado:
    df_f = df[df['Estado'].isin(estado_seleccionado)].copy()
else:
    df_f = df.copy()

# ---------------------------------------------------------
# 5. CÁLCULO DE MÉTRICAS GENERALES (CORREGIDO)
# ---------------------------------------------------------
total_registros = len(df_f)

# Conteos exactos verificando ABIERTA y CERRADA
cerrados = (df_f['Estado'] == 'CERRADA').sum()
pendientes = (df_f['Estado'] == 'ABIERTA').sum()

# Si por alguna razón hay estados distintos a ABIERTA/CERRADA, se contabilizan en pendientes
otros_estados = total_registros - (cerrados + pendientes)
if otros_estados > 0:
    pendientes += otros_estados

# Cálculo preciso de Tasa de Cierre
tasa_cierre = (cerrados / total_registros * 100) if total_registros > 0 else 0.0

# Conteo de Clasificaciones (Incidentes / Coyunturales)
incidentes = 0
coyunturales = 0

if 'Clasificacion' in df_f.columns:
    incidentes = df_f['Clasificacion'].str.contains('INCIDENTE', na=False).sum()
    coyunturales = df_f['Clasificacion'].str.contains('COYUNTURAL', na=False).sum()

# ---------------------------------------------------------
# 6. MOSTRAR MÉTRICAS EN PANTALLA
# ---------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Registros", total_registros)
with col2:
    st.metric("Pendientes / Abiertas", pendientes)
with col3:
    st.metric("Cerradas", cerrados)
with col4:
    st.metric("Tasa de Cierre", f"{tasa_cierre:.1f}%")

st.markdown("---")

# ---------------------------------------------------------
# 7. CHATBOT FLOTANTE OPTIMIZADO (GEMINI-3.6-FLASH CON STREAMING)
# ---------------------------------------------------------
gemini_key = st.secrets.get("GEMINI_API_KEY", "")

with st.popover("💬 Asistente IA SNC"):
    st.markdown("### 🤖 Asistente Virtual SNC")

    if not gemini_key:
        gemini_key = st.text_input(
            "Ingresa tu Gemini API Key:", type="password"
        )

    if gemini_key:
        try:
            genai.configure(api_key=gemini_key)

            if "gemini_messages" not in st.session_state:
                st.session_state.gemini_messages = []

            for msg in st.session_state.gemini_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            if user_prompt := st.chat_input("Escribe tu pregunta..."):
                st.session_state.gemini_messages.append(
                    {"role": "user", "content": user_prompt}
                )
                with st.chat_message("user"):
                    st.markdown(user_prompt)

                palabras_ignorar = {
                    "que", "del", "los", "las", "por", "con", "para", "documento",
                    "cedula", "nit", "numero", "snc", "colmedicos", "hola", "como",
                    "deberia", "tratar", "esta", "plan", "accion", "recomiendas",
                    "genero", "generó", "este", "quien", "quienes", "mas", "incidencias",
                    "usuarios", "colaboradores"
                }

                tokens = re.findall(r"\b[a-zA-Z0-9áéíóúÁÉÍÓÚñÑ]+\b", user_prompt)
                terminos_busqueda = [
                    t.lower()
                    for t in tokens
                    if t.lower() not in palabras_ignorar and len(t) >= 3
                ]

                coincidencias = pd.DataFrame()

                if terminos_busqueda:
                    pattern = "|".join(terminos_busqueda)
                    coincidencias = df_f[
                        df_f["_search_text"].str.contains(
                            pattern, case=False, na=False
                        )
                    ]

                resumen_colaboradores = ""
                if col_colaborador:
                    top_colab = (
                        df_f[col_colaborador[0]]
                        .value_counts()
                        .head(3)
                        .to_dict()
                    )
                    resumen_colaboradores = "\nTOP COLABORADORES CON MÁS CASOS:\n"
                    for colab, cant in top_colab.items():
                        resumen_colaboradores += f"- {colab}: {cant}\n"

                resumen_servicios = ""
                if "Servicio" in df_f.columns:
                    top_serv = df_f["Servicio"].value_counts().head(3).to_dict()
                    resumen_servicios = "\nTOP SERVICIOS CON MÁS CASOS:\n"
                    for serv, cant in top_serv.items():
                        resumen_servicios += f"- {serv}: {cant}\n"

                contexto_especifico = ""
                if not coincidencias.empty:
                    cols_limpias = [
                        c
                        for c in df_f.columns
                        if c not in ["Fecha_DT", "Periodo", "_search_text"]
                    ]
                    registros_encontrados = coincidencias[cols_limpias].head(
                        3
                    ).to_dict(orient="records")

                    contexto_especifico = "\n\nREGISTROS ENCONTRADOS:\n"
                    for idx, reg in enumerate(registros_encontrados, 1):
                        contexto_especifico += f"\n--- Caso #{idx} ---\n"
                        for k, v in reg.items():
                            if pd.notna(v) and str(v).strip() != "":
                                contexto_especifico += f"- {k}: {v}\n"

                contexto_snc = f"""
                Eres el Asistente de Gestión de Calidad (SNC) de COLMEDICOS.
                Responde de forma concisa, directa y estructurada.
                
                DATOS DE LA SESIÓN:
                - Total Registros: {total_registros} | Tasa Cierre: {tasa_cierre:.1f}%
                - Pendientes (Abiertas): {pendientes} | Cerradas: {cerrados}
                - Coyunturales: {coyunturales} | Incidentes: {incidentes}
                {resumen_colaboradores}
                {resumen_servicios}
                {contexto_especifico}
                """

                try:
                    # Modelo oficial gemini-3.6-flash optimizado con streaming
                    model = genai.GenerativeModel("gemini-3.6-flash")
                    prompt_completo = (
                        f"{contexto_snc}\n\nPregunta: {user_prompt}"
                    )

                    with st.chat_message("assistant"):
                        response_stream = model.generate_content(
                            prompt_completo, 
                            stream=True
                        )
                        
                        def stream_generator():
                            for chunk in response_stream:
                                yield chunk.text

                        full_response = st.write_stream(stream_generator)

                    st.session_state.gemini_messages.append(
                        {"role": "assistant", "content": full_response}
                    )
                except Exception as err:
                    st.error(f"Error al procesar la respuesta con la IA: {err}")
        except Exception as e:
            st.error("API Key inválida o no configurada correctamente.")
