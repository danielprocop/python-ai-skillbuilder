import json
import os
import uuid
from datetime import datetime
import logging

import boto3
from botocore.exceptions import ClientError
from google import genai  # assicurati di avere google-genai in requirements

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configurazione DynamoDB
TABLE_NAME = os.getenv("DYNAMODB_TABLE", "skillbuilder-skills")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

# Configurazione Gemini
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    logger.error("GOOGLE_API_KEY non impostata")
    # Falla subito se vuoi, oppure continua ma senza AI
    # raise RuntimeError("GOOGLE_API_KEY mancante")
try:
    gemini_client = genai.Client(api_key=API_KEY)
except Exception as e:
    logger.error("Errore inizializzazione Gemini client: %s", str(e))
    gemini_client = None

# Modello gemini
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

def lambda_handler(event, context):
    """
    Handler per 'chat skill': riceve { "user": "...", "message": "..." }
    Ritorna: 
      - statusCode 200 con JSON { added: [...], message: "...", aiRaw: {...} }
      - statusCode 400/500 in caso di errori.
    """
    logger.info("chat_skill invoked, event: %s", event)

    # Estraggo body JSON
    body_str = event.get("body", "{}")
    try:
        body = json.loads(body_str)
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Body non è JSON valido"})
        }

    user = body.get("user")
    message = body.get("message")
    if not user or not isinstance(message, str) or not message.strip():
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Campi 'user' e 'message' sono obbligatori e message non vuoto"})
        }

    # Se il client invia un parametro per livello o altre info, puoi estrarlo da body.
    # Ma qui consideriamo che l'AI estragga solo il nome della skill. Eventualmente si può chiedere livello.
    # Costruisco prompt per Gemini: chiedere estrazione di nuove skill apprese
    prompt = (
        "Analizza il seguente messaggio dell'utente. Se l'utente dichiara di aver appreso o migliorato "
        "una o più skill, restituisci un JSON con:\n"
        "  - action: \"learn_skill\" se c'è almeno una skill, altrimenti \"none\".\n"
        "  - skills: lista di nomi di skill (stringhe), se action è \"learn_skill\".\n"
        "\nEsempi di output:\n"
        "  { \"action\": \"learn_skill\", \"skills\": [\"Python\"] }\n"
        "  { \"action\": \"learn_skill\", \"skills\": [\"JavaScript\", \"SQL\"] }\n"
        "  { \"action\": \"none\" }\n"
        "\nNon includere altri campi. Restituisci solo il JSON puro.\n"
        f"Testo da analizzare: \"{message}\""
    )

    ai_raw = None
    extracted = {"action": "none"}
    if gemini_client is None:
        logger.warning("gemini_client non inizializzato, salto analisi AI.")
    else:
        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                # eventualmente config: temperature, max_tokens, ecc.
                temperature=0.3,
                max_tokens=200
            )
            ai_text = response.text.strip()
            ai_raw = ai_text
            logger.info("Risposta AI raw: %s", ai_text)
            # Provo a fare il parse JSON
            try:
                # Se l'AI aggiunge backticks o testo, potresti dover isolare il JSON: 
                # qui assumiamo che l'AI restituisca esattamente un JSON valido
                extracted = json.loads(ai_text)
            except json.JSONDecodeError:
                # Prova a estrarre parte che sembra JSON tra {...}
                # Cerca la prima occorrenza di {...}
                start = ai_text.find("{")
                end = ai_text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    snippet = ai_text[start:end+1]
                    try:
                        extracted = json.loads(snippet)
                    except:
                        logger.warning("Non sono riuscito a fare JSON.parse della risposta AI: %s", snippet)
                        extracted = {"action": "none"}
                else:
                    logger.warning("Risposta AI non JSON decodable: %s", ai_text)
                    extracted = {"action": "none"}
        except Exception as e:
            logger.error("Errore chiamata Gemini: %s", str(e))
            # Potresti scegliere di ritornare errore 500, o proseguire senza salvare.
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Errore durante analisi AI", "detail": str(e)})
            }

    # Ora, in base a extracted:
    added = []
    action = extracted.get("action")
    if action == "learn_skill":
        skills = extracted.get("skills")
        if isinstance(skills, list):
            for skill_name in skills:
                # Filtro skill_name: deve essere stringa non vuota
                if isinstance(skill_name, str) and skill_name.strip():
                    skill_clean = skill_name.strip()
                    # Costruisco item DynamoDB
                    skill_id = str(uuid.uuid4())
                    # Salvo data ISO o dd/mm/yyyy, come preferisci. Qui uso ISO
                    acquired_on = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                    item = {
                        "Skill_UID": skill_id,
                        "user": user,
                        "skill": skill_clean,
                        "level": 1,  # default, o potresti chiedere all'AI di stimare un livello?
                        "acquired_on": acquired_on,
                        "source": "chat",
                        "status": "done",
                        # salvo raw response per debug
                        "aiResponseRaw": ai_raw
                    }
                    try:
                        table.put_item(Item=item)
                        added.append({
                            "Skill_UID": skill_id,
                            "skill": skill_clean,
                            "acquired_on": acquired_on
                        })
                    except ClientError as e:
                        logger.error("Errore put_item chat_skill su skill %s: %s", skill_clean, e.response["Error"]["Message"])
                        # Non interrompo il loop: continuo con le altre skill
        else:
            logger.warning("Campo 'skills' non lista: %s", skills)
    else:
        # action none o altro campo: non fare nulla
        logger.info("Nessuna skill da salvare (action=%s)", action)

    # Risposta HTTP
    resp_body = {
        "added": added, 
        "message": None,
        "aiRaw": ai_raw
    }
    if added:
        resp_body["message"] = f"Aggiunte {len(added)} skill al diario."
    else:
        resp_body["message"] = "Non ho individuato nuove skill da salvare."
    # Rimuovi aiRaw dalla response se non vuoi esporlo al client
    return {
        "statusCode": 200,
        "body": json.dumps(resp_body)
    }
