import os
import time
import streamlit as st
import datetime
from dotenv import load_dotenv
 
from google import genai
from google.genai import types
 
from tools import (
    crear_ticket_en_jira,
    agendar_reunion_en_google_calendar,
    actualizar_contacto_en_crm,
)
 
FECHA_ACTUAL = datetime.datetime.now().strftime("%d de %B de %Y")
 
load_dotenv()
 
st.set_page_config(page_title="UTP Assistant", page_icon="🤖", layout="wide")
 
# --- Estilos ligeros ---------------------------------------------------
st.markdown(
    """
    <style>
    .block-container { max-width: 820px; padding-top: 2rem; }
    [data-testid="stChatMessage"] { border-radius: 14px; padding: 0.4rem 0.2rem; }
    .badge {
        display: inline-block; padding: 3px 10px; border-radius: 999px;
        font-size: 0.78rem; margin-bottom: 6px; margin-right: 4px;
    }
    .badge-ok { background: #133a2b; color: #6fe3a3; }
    .badge-mock { background: #3a3213; color: #e3c96f; }
    </style>
    """,
    unsafe_allow_html=True,
)
 
st.title("🤖 UTP Assistant")
st.caption("Lee correos de clientes y ejecuta las acciones correspondientes en Jira, Google Calendar y el CRM.")
 
SYSTEM_INSTRUCTION = f"""
Eres UTP Assistant, un agente interno de UTP Consult.
CONTEXTO TEMPORAL: Hoy es {FECHA_ACTUAL}. Utiliza este año (2026) para cualquier cálculo de fechas a menos que el cliente especifique otro año.
 
Tu trabajo es leer correos de clientes o prospectos y extraer las acciones
concretas que se deben ejecutar en los sistemas internos:
 
- Si detectas un requerimiento o problema técnico que debe resolverse,
  crea un ticket en Jira con crear_ticket_en_jira.
- Si detectas la intención de agendar una reunión o llamada, agenda el
  evento con agendar_reunion_en_google_calendar. Si falta información
  (fecha, hora, correos de participantes), pide una aclaración antes de
  inventar datos.
- Si el correo menciona un nuevo contacto o requerimientos clave de un
  cliente, regístralo con actualizar_contacto_en_crm.
 
Sé proactivo: invoca todas las herramientas que apliquen para un mismo
correo si corresponde (por ejemplo, un ticket Y una reunión). Si algo es
ambiguo, pregunta antes de actuar.
 
Al final, responde con un resumen claro y breve, en español, de las
acciones que tomaste para el equipo interno. Cuando una herramienta te
devuelva un campo "link", inclúyelo en el resumen como un enlace en
formato Markdown (ejemplo: [Ver ticket en Jira](link),
[Ver evento en Calendar](link)). Usa únicamente los links que te
devuelvan las herramientas; nunca inventes uno.
"""
 
EMAIL_PRUEBA = (
    "Hola equipo de UTP Consult, gracias por la propuesta. Antes de avanzar, "
    "necesitamos que revisen un error crítico que está bloqueando la carga de "
    "reportes en el módulo de facturación (prioridad alta). Además, nos "
    "gustaría agendar una reunión de seguimiento el viernes 25 de septiembre "
    "a las 3pm con nuestro equipo (ana.torres@techcorp.com). Saludos, Ana Torres, "
    "TechCorp."
)
 
AVATAR_USER = "🧑‍💼"
AVATAR_BOT = "🤖"
 
# ---------------------------------------------------------------------------
# Declaraciones de las herramientas (schema manual, en vez de pasar las
# funciones de Python directamente). Esto es lo que nos da control manual
# sobre cuándo se ejecutan.
# ---------------------------------------------------------------------------
 
FUNCTION_DECLARATIONS = [
    {
        "name": "crear_ticket_en_jira",
        "description": "Crea un ticket en Jira para un requerimiento o problema técnico detectado en el correo.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "titulo": {"type": "STRING", "description": "Título breve y claro del ticket."},
                "descripcion": {"type": "STRING", "description": "Descripción detallada del requerimiento."},
                "prioridad": {
                    "type": "STRING",
                    "description": "Prioridad del ticket.",
                    "enum": ["Highest", "High", "Medium", "Low", "Lowest"],
                },
            },
            "required": ["titulo", "descripcion", "prioridad"],
        },
    },
    {
        "name": "agendar_reunion_en_google_calendar",
        "description": "Agenda una reunión real en Google Calendar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "asunto": {"type": "STRING", "description": "Título de la reunión."},
                "fecha_tentativa": {
                    "type": "STRING",
                    "description": 'Fecha y hora de inicio en formato ISO 8601, ej. "2026-09-25T15:00:00-05:00".',
                },
                "participantes": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Lista de correos electrónicos de los invitados.",
                },
            },
            "required": ["asunto", "fecha_tentativa", "participantes"],
        },
    },
    {
        "name": "actualizar_contacto_en_crm",
        "description": "Registra o actualiza un contacto en el CRM (simulado).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "nombre_contacto": {"type": "STRING", "description": "Nombre del contacto o cliente."},
                "empresa": {"type": "STRING", "description": "Empresa a la que pertenece el contacto."},
                "requerimientos_clave": {"type": "STRING", "description": "Resumen de requerimientos detectados."},
            },
            "required": ["nombre_contacto", "empresa", "requerimientos_clave"],
        },
    },
]
 
TOOL_MAP = {
    "crear_ticket_en_jira": crear_ticket_en_jira,
    "agendar_reunion_en_google_calendar": agendar_reunion_en_google_calendar,
    "actualizar_contacto_en_crm": actualizar_contacto_en_crm,
}
 
MAX_REINTENTOS = 3
 
 
@st.cache_resource
def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
 
 
def crear_chat():
    client = get_client()
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[types.Tool(function_declarations=FUNCTION_DECLARATIONS)],
    )
    return client.chats.create(model="gemini-3.6-flash", config=config)
 
 
def _enviar_con_reintentos(chat, contenido):
    """Envía contenido al chat reintentando solo ante errores transitorios (503/500)."""
    ultimo_error = None
    for intento in range(MAX_REINTENTOS):
        try:
            return chat.send_message(contenido)
        except Exception as e:
            ultimo_error = e
            mensaje = str(e)
            if "503" in mensaje or "UNAVAILABLE" in mensaje or "500" in mensaje:
                time.sleep(2 * (intento + 1))
                continue
            raise
    raise ultimo_error
 
 
def _resumen_de_respaldo(resultados_acciones):
    """Arma un resumen sin depender del modelo, usando los resultados ya obtenidos."""
    lineas = [
        "No pude generar el resumen con el modelo (el servicio de Gemini está "
        "saturado en este momento), pero estas acciones sí se completaron:"
    ]
    for item in resultados_acciones:
        r = item["resultado"]
        if r.get("status") in ("success", "scheduled", "updated"):
            link = f" — {r['link']}" if r.get("link") else ""
            lineas.append(f"- **{r.get('sistema', item['herramienta'])}**: {r.get('status')}{link}")
        else:
            lineas.append(f"- **{item['herramienta']}**: error ({r.get('detalle', 'desconocido')})")
    return "\n".join(lineas)
 
 
def procesar_mensaje(chat, user_input):
    """
    Ciclo manual de function calling:
    1) Envía el mensaje del usuario.
    2) Si el modelo pide ejecutar herramientas, las ejecuta UNA sola vez.
    3) Si la síntesis final falla tras los reintentos, arma un resumen de
       respaldo con los resultados ya obtenidos (sin repetir ninguna acción).
    """
    resultados_acciones = []
    response = _enviar_con_reintentos(chat, user_input)
 
    while getattr(response, "function_calls", None):
        function_response_parts = []
        for llamada in response.function_calls:
            func = TOOL_MAP.get(llamada.name)
            if func is None:
                resultado = {"status": "error", "detalle": f"Herramienta desconocida: {llamada.name}"}
            else:
                resultado = func(**llamada.args)
            resultados_acciones.append({"herramienta": llamada.name, "resultado": resultado})
            function_response_parts.append(
                types.Part.from_function_response(name=llamada.name, response=resultado)
            )
        try:
            response = _enviar_con_reintentos(chat, function_response_parts)
        except Exception:
            return _resumen_de_respaldo(resultados_acciones)
 
    return response.text
 
 
if "chat" not in st.session_state:
    st.session_state.chat = crear_chat()
if "messages" not in st.session_state:
    st.session_state.messages = []
 
with st.sidebar:
    st.subheader("Estado de integraciones")
    st.markdown(
        '<span class="badge badge-ok">🟢 Jira: real</span>'
        '<span class="badge badge-ok">🟢 Calendar: real</span>'
        '<span class="badge badge-mock">🟡 CRM: simulado</span>',
        unsafe_allow_html=True,
    )
    st.divider()
    st.subheader("Prueba rápida")
    st.caption("Carga el correo de ejemplo de la consigna con un clic.")
    if st.button("📧 Cargar correo de prueba", use_container_width=True):
        st.session_state.pending_input = EMAIL_PRUEBA
    if st.button("🗑️ Limpiar conversación", use_container_width=True):
        st.session_state.chat = crear_chat()
        st.session_state.messages = []
        st.rerun()
 
for msg in st.session_state.messages:
    avatar = AVATAR_USER if msg["role"] == "user" else AVATAR_BOT
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])
 
user_input = st.chat_input("Pega aquí el correo del cliente...")
 
if "pending_input" in st.session_state:
    user_input = st.session_state.pop("pending_input")
 
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar=AVATAR_USER):
        st.markdown(user_input)
 
    with st.chat_message("assistant", avatar=AVATAR_BOT):
        with st.spinner("Procesando correo y ejecutando acciones..."):
            try:
                respuesta = procesar_mensaje(st.session_state.chat, user_input)
            except Exception as e:
                respuesta = f"Ocurrió un error al procesar el correo: {e}"
        st.markdown(respuesta)
 
    st.session_state.messages.append({"role": "assistant", "content": respuesta})