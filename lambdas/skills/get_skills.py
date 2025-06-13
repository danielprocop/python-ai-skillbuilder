import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = "skillbuilder-skills"
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    logger.info("Fetching all skills")

    response = table.scan()
    skills = response.get("Items", [])

    return {
        "statusCode": 200,
        "body": json.dumps(skills)
    }
