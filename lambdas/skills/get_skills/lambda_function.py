import json  # Modulo per serializzare/deserializzare oggetti JSON
import boto3  # SDK AWS per interagire con servizi come DynamoDB
import logging  # Modulo per logging

# Configura il logger di default
logger = logging.getLogger()  
logger.setLevel(logging.INFO)  # Imposta il livello di log a INFO

# Nome della tabella DynamoDB
TABLE_NAME = "skillbuilder-skills"

# Istanzia la risorsa DynamoDB usando le credenziali/config AWS già presenti
dynamodb = boto3.resource("dynamodb")
# Ottiene l’oggetto Table per operazioni su TABLE_NAME
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    # Logga un messaggio informativo all’inizio della funzione
    logger.info("Fetching all skills")

    # Esegue una scansione completa della tabella per ottenere tutti gli item
    response = table.scan()
    # Estrae la lista di item (chiave "Items"); se mancante, usa lista vuota
    skills = response.get("Items", [])

    # Restituisce un oggetto HTTP-like con codice 200 e body JSON con i dati
    return {
        "statusCode": 200,
        "body": json.dumps(skills, default=str)  # default=str per serializzare tipi non standard
    }
