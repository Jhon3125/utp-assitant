"""
app.py
Interfaz Streamlit para UTP Assistant.
El SDK de Gemini (google-genai) maneja el ciclo de function calling
de forma automática: basta con pasarle las funciones de tools.py.
"""

import os
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

st.set_page_config(page_title="UTP Assistant", page_icon="🤖")
st.title("🤖 UTP Assistant")

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
ambiguo, pregunta antes de actuar. Al final, responde con un resumen claro
y breve, en español, de las acciones que tomaste para el equipo interno.
"""

EMAIL_PRUEBA = (
    "Hola equipo de UTP Consult, gracias por la propuesta. Antes de avanzar, "
    "necesitamos que revisen un error crítico que está bloqueando la carga de "
    "reportes en el módulo de facturación (prioridad alta). Además, nos "
    "gustaría agendar una reunión de seguimiento el viernes 25 de septiembre "
    "a las 3pm con nuestro equipo (ana.torres@techcorp.com). Saludos, Ana Torres, "
    "TechCorp."
)


@st.cache_resource
def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def crear_chat():
    client = get_client()
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[
            crear_ticket_en_jira,
            agendar_reunion_en_google_calendar,
            actualizar_contacto_en_crm,
        ],
    )
    return client.chats.create(model="gemini-3.6-flash", config=config)


if "chat" not in st.session_state:
    st.session_state.chat = crear_chat()
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("Prueba rápida")
    st.caption("Carga el correo de ejemplo de la consigna con un clic.")
    if st.button("Cargar correo de prueba"):
        st.session_state.pending_input = EMAIL_PRUEBA

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Pega aquí el correo del cliente...")

if "pending_input" in st.session_state:
    user_input = st.session_state.pop("pending_input")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Procesando correo y ejecutando acciones..."):
            try:
                response = st.session_state.chat.send_message(user_input)
                respuesta = response.text
            except Exception as e:
                respuesta = f"Ocurrió un error al procesar el correo: {e}"
        st.markdown(respuesta)

    st.session_state.messages.append({"role": "assistant", "content": respuesta})
