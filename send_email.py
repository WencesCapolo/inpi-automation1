import openai
import requests
import json
import os
import time
import random
from typing import Optional

# ------------------------------------------------------------------
# Helper to retrieve secrets consistently (Streamlit-like behaviour)
# ------------------------------------------------------------------

def _load_toml_secret(key: str) -> Optional[str]:
    """Attempt to read a value from .streamlit/secrets.toml if present."""
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    if not os.path.exists(secrets_path):
        return None

    try:
        try:
            import tomllib  # Python 3.11+
            with open(secrets_path, "rb") as f:
                secrets_dict = tomllib.load(f)
        except ModuleNotFoundError:
            import toml  # type: ignore
            secrets_dict = toml.load(secrets_path)
        return secrets_dict.get(key)
    except Exception:
        # If parsing fails, fall back gracefully
        return None


def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:

    try:
        import streamlit as st  # noqa: F401
        # If imported successfully, we're likely in a Streamlit environment
        return st.secrets.get(key, default)  # type: ignore[attr-defined]
    except Exception:
        pass

    # 2️⃣ Environment variable
    env_val = os.getenv(key)
    if env_val:
        return env_val

    # 3️⃣ Local secrets.toml fallback
    toml_val = _load_toml_secret(key)
    if toml_val is not None:
        return toml_val

    # 4️⃣ Default
    return default


openai.api_key = get_secret("OPENAI_API_KEY")
BREVO_API_KEY = get_secret("BREVO_API_KEY")
BREVO_URL = get_secret("BREVO_URL") or "https://api.brevo.com/v3/smtp/email"
WHATSAPP_PHONE = get_secret("WHATSAPP_PHONE", "5493512017052")

def generate_email_content(record: dict) -> str:
    """Generate personalized email content for a single record using OpenAI."""
    
    # Determine if it's VISTA or OPOSICIÓN based on origen field
    origen = record.get('origen', '').upper()
    is_vista = 'VISTA' in origen
    is_oposicion = 'OPOSICION' in origen
    
    # Set appropriate terminology and legal context
    if is_vista:
        procedimiento_tipo = "vista"
        procedimiento_nombre = "Vista"
        accion_descripcion = "recibió una vista"
        ley_articulo = "Art. 21 de la Ley 22.362"
        explicacion_legal = "La vista es un procedimiento donde el INPI solicita aclaraciones o documentación adicional sobre su solicitud de marca. Es una oportunidad para completar o corregir aspectos de su presentación antes de la decisión final."
    else:  # Default to oposición
        procedimiento_tipo = "oposición"
        procedimiento_nombre = "Oposición"
        accion_descripcion = "recibió una oposición"
        ley_articulo = "Art. 17 de la Ley 22.362"
        explicacion_legal = "La oposición es un procedimiento donde un tercero se opone al registro de su marca por considerar que puede afectar sus derechos. Usted tiene derecho a presentar una contestación para defender su solicitud."
    
    prompt = f"""
    Actúa como un abogado especialista en propiedad intelectual en Argentina, que trabaja para el estudio jurídico Eguía Marcas y Patentes, líder en registros de marcas. Escribe un email claro, profesional y persuasivo, destinado a un titular de una marca que {accion_descripcion} a su solicitud ante el INPI.

    Objetivo: Ofrecer nuestros servicios como representantes legales para acompañarlo en el proceso de defensa y registro exitoso de su marca.

    Datos del caso:
    - Nombre del titular: {record.get('Titulares', 'N/A')}
    - Denominación de la marca: {record.get('Denominacion', 'N/A')}
    - Clase: {record.get('Clase', 'N/A')}
    - Número de acta: {record.get('Acta', 'N/A')}
    - Fecha de publicación: {record.get('Fecha', 'N/A')}
    - Artículo de la ley: {record.get('Art.Ley', 'N/A')}
    - Tipo de procedimiento: {procedimiento_nombre}
    - Fundamento legal: {ley_articulo}

    Contexto legal:
    {explicacion_legal}

    Instrucciones:
    - Comienza con un saludo personalizado (usa el nombre completo del titular).
    - Informa con precisión que su marca "{record.get('Denominacion', 'N/A')}", clase {record.get('Clase', 'N/A')}, ha {accion_descripcion} en el proceso de registro ante el INPI.
    - Explica brevemente qué significa una {procedimiento_tipo} basándote en el contexto legal proporcionado.
    - Menciona el artículo de la ley: {record.get('Art.Ley', 'N/A')} solo si no es N/A y explica brevemente qué significa.
    - Explica las implicancias que tiene (puede ser que no se registre la marca).
    - Presenta a Eguía Marcas y Patentes como un equipo experto en defensa de marcas con amplia experiencia en resolver {procedimiento_tipo}s.
    - Ofrece una consulta gratuita para analizar el caso sin compromiso.
    - Muestra empatía y transmite seguridad profesional.
    - Firma como "Eguía Marcas y Patentes".
    - No escribas un asunto.

    Tono: Profesional, cercano, claro, sin tecnicismos innecesarios. Evita sonar como spam. La redacción debe invitar al titular a responder o agendar una llamada.
    """

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Eres un abogado experto en propiedad intelectual argentina con conocimiento profundo de la Ley 22.362 de Marcas y Designaciones."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=800
    )

    return str(response.choices[0].message.content).strip()


def send_email_via_brevo(email_content: str, record: dict) -> None:
    """Send email using Brevo API for a given record."""
    recipient_email = record.get('email_found')
    if not recipient_email:
        print(f"[SKIP] Acta {record.get('Acta')} – no email address found.")
        return

    # Determine subject based on procedure type
    origen = record.get('origen', '').upper()
    if 'VISTA' in origen:
        subject = f"Vista a su marca '{record.get('Denominacion', 'N/A')}' - Eguía Marcas y Patentes"
    else:
        subject = f"Oposición a su marca '{record.get('Denominacion', 'N/A')}' - Eguía Marcas y Patentes"

    html_content = f"""
    <html>
    <head>
        <meta charset=\"UTF-8\">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .logo {{ text-align: center; margin-bottom: 50px; }}
            .content {{ margin: 20px 0; }}
            .whatsapp-cta {{ text-align: center; margin: 30px 0; }}
            .whatsapp-btn {{ display: inline-block; background-color: #25D366; color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; font-size: 16px; transition: background-color 0.3s; }}
            .whatsapp-btn:hover {{ background-color: #1da851; }}
            .footer {{ margin-top: 40px; padding-top: 20px; border-top: 2px solid #1f4e79; font-size: 12px; color: #666; }}
            .footer strong {{ color: #1f4e79; }}
        </style>
    </head>
    <body>
        <div class="logo">
            <img src="https://img.mailinblue.com/7745606/images/content_library/original/6761d49966ad09c26501c34d.png" 
                 alt="Eguía Marcas y Patentes Logo" 
                 style="max-width: 250px; height: auto;">
        </div>
        <div class=\"content\">
            {email_content.replace(chr(10), '<br>') if email_content else ''}
            <div class=\"whatsapp-cta\">
                <a href=\"https://api.whatsapp.com/send?phone={WHATSAPP_PHONE}\" class=\"whatsapp-btn\" target=\"_blank\">📱 Contactar por WhatsApp</a>
            </div>
        </div>
        <div class=\"footer\">
            <strong>Nicolas Eguía Cima</strong><br>
            Dirección<br><br>
            <strong>Móvil:</strong> +54 9 351 5114133<br>
            <strong>Teléfono:</strong> +54 0351 4812200<br><br>
            Tristán Malbrán 4011 - Piso 2 Of. 1<br>
            Cerro de las Rosas - CP: 5009ACE - Córdoba - Argentina<br><br>
            <strong>Redes:</strong> @eguiamarcasypatentes<br><br>
            <em>CÓRDOBA - ROSARIO - MENDOZA - BUENOS AIRES - LA RIOJA - TUCUMÁN</em>
        </div>
    </body>
    </html>
    """

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": BREVO_API_KEY
    }
    
    payload = {
        "sender": {
            "name": "Eguía Marcas y Patentes",
            "email": "nicolas@eguia.com.ar"
        },
        "replyTo": {
                    "name": "Eguía Marcas y Patentes",
                    "email": "fgarzon@eguia.com.ar"
                },
        "to": [
            {
                "email": recipient_email,
                "name": record.get('Titulares', 'Cliente')
            }
        ],
        "subject": subject,
        "htmlContent": html_content
    }
    
    try:
        response = requests.post(BREVO_URL, headers=headers, data=json.dumps(payload))
        if response.status_code == 201:
            print(f"[SUCCESS] Email sent to {recipient_email} (Acta {record.get('Acta')})")
        else:
            print(f"[ERROR] Failed to send email to {recipient_email}. Status: {response.status_code}. Response: {response.text}")
    except Exception as e:
        print(f"[EXCEPTION] Error sending email to {recipient_email}: {e}")


if __name__ == "__main__":
    # Load JSON data
    try:
        with open("comprehensive_data_export_20250710_121444.json", "r", encoding="utf-8") as f:
            dataset = json.load(f)
    except FileNotFoundError:
        print("comprehensive_data_export_20250710_121444.json not found. Ensure the file exists in the script directory.")
        exit(1)

    records = dataset.get("records", [])
    print(f"Total records: {len(records)}")

    for idx, record in enumerate(records, 1):
        email = record.get("email_found")
        if not email:
            print(f"[{idx}/{len(records)}] Skipping Acta {record.get('Acta')} – no email.")
            continue

        print(f"[{idx}/{len(records)}] Processing Acta {record.get('Acta')} – sending to {email}...")
        try:
            content = generate_email_content(record)
            send_email_via_brevo(content, record)
            # Respectful delay to avoid hitting rate limits
            time.sleep(random.uniform(1.0, 2.0))
        except Exception as e:
            print(f"[EXCEPTION] Error processing Acta {record.get('Acta')}: {e}")
            continue

    print("\n=== Email sending routine completed ===")
