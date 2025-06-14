import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = "skillbuilder-skills"
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    skill_id = event["pathParameters"]["id"]
    logger.info(f"Deleting skill with ID: {skill_id}")

    response = table.delete_item(
        Key={"Skill_UID": skill_id},
        ReturnValues="ALL_OLD"
    )

    if "Attributes" in response:
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Skill deleted"})
        }
    else:
        return {
            "statusCode": 404,
            "body": json.dumps({"message": "Skill not found"})
        }
