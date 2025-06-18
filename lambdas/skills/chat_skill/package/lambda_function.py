import os
import json
from datetime import datetime
from google import genai
import boto3  # usato se salvi su DynamoDB; boto3 è incluso nel runtime
# Se usi RDS/SQL, importa qui psycopg2 o SQLAlchemy

# Inizializza client Gemini una sola volta (fuori dall'handler per riuso in esecuzioni successive calde)
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
# Modello da usare (scegli in base a quanto è disponibile nel tuo account free tier)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Configura client Google Gen AI
if not GEMINI_API_KEY:
    raise RuntimeError("Manca GOOGLE_API_KEY nelle variabili d'ambiente")
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    # In fase di deploy, se Google Gen AI SDK non è incluso correttamente, si fallirà qui
    raise

# Configura DB: ad esempio DynamoDB
DYNAMO_TABLE = os.getenv("SKILLS_TABLE")  # nome tabella inserito in env vars
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(DYNAMO_TABLE)

def lambda_handler(event, context):
    """
    handler per chat-skill: esegue parsing del messaggio libero, chiama Gemini per estrarre skill,
    e salva ogni skill nel DB DynamoDB.
    Ci si aspetta evento API Gateway proxy integration:
    event["body"] è stringa JSON con almeno {"userId": "...", "message": "..."}.
    """
    try:
        # 1. Verifica metodo HTTP: accettiamo solo POST
        http_method = event.get("httpMethod")
        if http_method != "POST":
            return {
                "statusCode": 405,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Metodo non consentito, usa POST"})
            }
        # 2. Leggi e parsa body JSON
        body_str = event.get("body")
        if not body_str:
            raise ValueError("Body mancante")
        try:
            body = json.loads(body_str)
        except json.JSONDecodeError:
            raise ValueError("JSON non valido nel body")
        # 3. Estrai userId e message
        user_id = body.get("userId") or body.get("user_id")
        message_text = body.get("message")
        if not user_id or not message_text:
            raise ValueError("Campi 'userId' e 'message' richiesti")
        # 4. Costruisci prompt per Gemini
        # Per la data odierna in ISO, nel fuso server (si può migliorare includendo fuso Europe/Rome se necessario)
        today_iso = datetime.utcnow().strftime("%Y-%m-%d")
        prompt = (
            "Sei un assistente in italiano. Ricevi un messaggio utente e devi estrarre se contiene informazioni "
            "su una o più skill apprese. Se trovi una o più skill, restituisci solo un JSON valido (array) in questo formato:\n"
            "[\n"
            '  { "skill": "nome", "level": 1, "description": "...", "date": "YYYY-MM-DD" },\n'
            "  ...\n"
            "]\n"
            "Campi opzionali (level, description, date) ometti o usa null se non presenti. Se date non specificata, usa la data odierna.\n"
            "Se l'utente menziona più skill, usa un array con più oggetti. Se nessuna skill, restituisci un array vuoto: [].\n"
            "Rispondi in italiano e NON inviare testo extra oltre al JSON puro.\n"
            f"Data odierna: {today_iso}.\n"
            f"Esempi:\n"
            "- “Oggi ho imparato React e Redux” → `[{{\"skill\":\"React\"}},{{\"skill\":\"Redux\"}}]`\n"
            "- “Ho migliorato Python, livello 7, scrivendo script di automazione” → `[{{\"skill\":\"Python\",\"level\":7,\"description\":\"scrivendo script di automazione\",\"date\":\"{today_iso}\"}}]`\n"
            f"Messaggio utente: \"{message_text}\""
        )
        # 5. Chiamata a Gemini via SDK
        # Usiamo chat.create per generare risposta; si può anche usare client.models.generate_content
        # Qui esempio con chat API:
        chat = client.chats.create(model=GEMINI_MODEL)
        response = chat.send_message(prompt)
        raw_text = response.text.strip()
        # 6. Parsing del JSON restituito
        try:
            skill_array = json.loads(raw_text)
            if not isinstance(skill_array, list):
                # Se non è array, trattiamo come zero risultati
                skill_array = []
        except json.JSONDecodeError:
            # Se non parseabile, consideriamo che non abbia trovato skill
            skill_array = []
        # 7. Per ciascuna skill estratta, salviamo in DB
        saved_items = []
        for item in skill_array:
            # Ogni item dovrebbe essere un dict con almeno "skill"
            name = item.get("skill")
            if not name or not isinstance(name, str):
                continue
            name = name.strip()
            if not name:
                continue
            # Livello opzionale
            level = item.get("level")
            if level is not None:
                try:
                    level = int(level)
                    if not (1 <= level <= 10):
                        level = None
                except:
                    level = None
            # Descrizione opzionale
            description = item.get("description")
            if description is not None:
                description = description.strip()
                # Facoltativo: tronca se troppo lunga
                if len(description) > 500:
                    description = description[:500]
            # Data opzionale
            date_str = item.get("date")
            # Verifica formato YYYY-MM-DD
            try:
                # Se non fornita o formato errato, usiamo today_iso
                if isinstance(date_str, str):
                    # semplice validazione: lunghezza 10 e caratteri
                    parts = date_str.split("-")
                    if len(parts) == 3 and len(parts[0])==4:
                        learned_date = date_str
                    else:
                        learned_date = today_iso
                else:
                    learned_date = today_iso
            except:
                learned_date = today_iso
            # Costruisci item DynamoDB simile a add_skill
            import uuid
            skill_id = str(uuid.uuid4())
            db_item = {
                "userId": str(user_id),
                "skillId": skill_id,
                "skillName": name,
                "learnedDate": learned_date
            }
            if level is not None:
                db_item["level"] = level
            if description:
                db_item["description"] = description
            # Salva su DynamoDB
            try:
                table.put_item(Item=db_item)
                saved_items.append(db_item)
            except Exception as e:
                # Log dell’errore ma continua con le altre
                print(f"Errore salvataggio skill {name}: {e}")
        # 8. Costruisci messaggio di risposta
        if saved_items:
            names = ", ".join([item["skillName"] for item in saved_items])
            ai_message = f"Ho salvato la/le skill: {names}."
        else:
            ai_message = "Non ho individuato alcuna skill nel tuo messaggio. Puoi specificare cosa hai imparato?"
        # 9. Ritorna risposta HTTP
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "aiMessage": ai_message,
                "savedSkills": saved_items
            })
        }
    except ValueError as ve:
        # Errori di validazione input
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(ve)})
        }
    except Exception as e:
        print("Errore in chat_skill:", str(e))
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Errore interno"})
        }
