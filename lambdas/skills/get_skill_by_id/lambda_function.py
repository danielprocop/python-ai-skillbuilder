import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = "skillbuilder-skills"
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    logger(event)
    skill_id = event["pathParameters"]["id"]
    logger.info(f"Fetching skill with ID: {skill_id}")

    response = table.get_item(Key={"Skill_UID": skill_id})
    item = response.get("Item")

    if item:
        return {
            "statusCode": 200,
            "body": json.dumps(item, default=str)
        }
    else:
        return {
            "statusCode": 404,
            "body": json.dumps({"message": "Skill not found"})
        }

