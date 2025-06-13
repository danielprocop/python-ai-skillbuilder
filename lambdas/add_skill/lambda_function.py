import json
from datetime import date
import uuid
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = "skillbuilder-skills" #definisce il nome della tabella DynamoDB
dynamodb = boto3.resource("dynamodb") #inizializza l oggetto che comunica con DynamoDB.
table = dynamodb.Table(TABLE_NAME) #serve per ottenere un riferimento alla tabella DynamoDB

def lambda_handler(event, context):
    logger.info("Lambda invoked with event: %s", event)
    
    #event è un dizionario chiave: valore
    body_json=event.get("body", "{}") #prende il valore della chiave body dal dizionario, se non trova la chiave restituisce {} 
    body = json.loads(body_json) #carica il valore dal json alla variabile, da json string => dizionario python

    skill = {
        "Skill_UID": str(uuid.uuid4()), 
        "name": body.get("name","user_undefined"),
        "level": body.get("level", 1),
        "acquired_on": date.today().strftime("%d/%m/%Y")
    }

    table.put_item(Item=skill)

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Skill added", "skill": skill}) # fa il contrario della loads dizionario python => json string
    }


    