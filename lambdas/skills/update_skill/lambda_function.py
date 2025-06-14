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
    body = json.loads(event.get("body", "{}"))

    logger.info(f"Updating skill {skill_id} with body: {body}")

    update_expression = []
    expression_values = {}
    for key in ["user", "skill", "level", "acquired_on"]:
        if key in body:
            update_expression.append(f"{key} = :{key}")
            expression_values[f":{key}"] = body[key]

    if not update_expression:
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "No valid fields to update"})
        }

    update_expr = "SET " + ", ".join(update_expression)

    response = table.update_item(
        Key={"Skill_UID": skill_id},
        UpdateExpression=update_expr,
        ExpressionAttributeValues=expression_values,
        ReturnValues="ALL_NEW"
    )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Skill updated",
            "skill": response.get("Attributes", {})
        })
    }
