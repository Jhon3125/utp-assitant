"""
tools.py
Funciones (herramientas) que UTP Assistant puede invocar mediante function calling.
- Jira: integración real vía REST API.
- Google Calendar: integración real vía OAuth2.
- CRM: simulado (mock).
"""

import os
import datetime
import requests
from requests.auth import HTTPBasicAuth

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# 1. JIRA (REAL)
# ---------------------------------------------------------------------------

load_dotenv()

JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")


def crear_ticket_en_jira(titulo: str, descripcion: str, prioridad: str) -> dict:
    """
    Crea un ticket real en Jira a partir de un requerimiento detectado en un correo.

    Args:
        titulo: Título breve y claro del ticket.
        descripcion: Descripción detallada del requerimiento del cliente.
        prioridad: Prioridad del ticket. Debe ser una de:
            "Highest", "High", "Medium", "Low", "Lowest".

    Returns:
        dict con el estado de la operación, el ID del ticket creado y el sistema usado.
    """
    url = f"{JIRA_URL}/rest/api/3/issue"

    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": titulo,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": descripcion}],
                    }
                ],
            },
            "issuetype": {"name": "Task"},
            "priority": {"name": prioridad},
        }
    }

    try:
        resp = requests.post(
            url,
            json=payload,
            auth=HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN),
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        print(f"[JIRA] Ticket creado: {data.get('key')}")
        return {"status": "success", "ticket_id": data.get("key"), "sistema": "Jira"}
    except requests.exceptions.RequestException as e:
        print(f"[JIRA] Error al crear ticket: {e}")
        return {"status": "error", "sistema": "Jira", "detalle": str(e)}


# ---------------------------------------------------------------------------
# 2. GOOGLE CALENDAR (REAL)
# ---------------------------------------------------------------------------

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_calendar_service():
    """Maneja el flujo OAuth2 y devuelve un cliente autenticado de Calendar."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def agendar_reunion_en_google_calendar(asunto: str, fecha_tentativa: str, participantes: list) -> dict:
    """
    Agenda una reunión real en Google Calendar (duración por defecto: 1 hora).

    Args:
        asunto: Título de la reunión.
        fecha_tentativa: Fecha y hora de inicio en formato ISO 8601,
            por ejemplo "2026-09-25T15:00:00-05:00".
        participantes: Lista de correos electrónicos de los invitados.

    Returns:
        dict con el estado de la operación, el ID del evento creado y el sistema usado.
    """
    try:
        service = _get_calendar_service()
        inicio = datetime.datetime.fromisoformat(fecha_tentativa)
        fin = inicio + datetime.timedelta(hours=1)

        evento = {
            "summary": asunto,
            "start": {"dateTime": inicio.isoformat()},
            "end": {"dateTime": fin.isoformat()},
            "attendees": [{"email": correo} for correo in participantes],
        }

        resultado = service.events().insert(calendarId="primary", body=evento).execute()
        print(f"[CALENDAR] Evento creado: {resultado.get('id')}")
        return {"status": "scheduled", "event_id": resultado.get("id"), "sistema": "Google Calendar"}
    except Exception as e:
        print(f"[CALENDAR] Error al agendar: {e}")
        return {"status": "error", "sistema": "Google Calendar", "detalle": str(e)}


# ---------------------------------------------------------------------------
# 3. CRM (SIMULADO)
# ---------------------------------------------------------------------------

def actualizar_contacto_en_crm(nombre_contacto: str, empresa: str, requerimientos_clave: str) -> dict:
    """
    Registra o actualiza un contacto en el CRM. Simulado para este prototipo.

    Args:
        nombre_contacto: Nombre del contacto o cliente.
        empresa: Empresa a la que pertenece el contacto.
        requerimientos_clave: Resumen breve de los requerimientos detectados en el correo.

    Returns:
        dict con el estado simulado de la operación.
    """
    print(f"[CRM SIMULADO] Contacto: {nombre_contacto} | Empresa: {empresa} | Requerimientos: {requerimientos_clave}")
    return {"status": "updated", "crm_id": "CRM-551", "sistema": "CRM (simulado)"}
