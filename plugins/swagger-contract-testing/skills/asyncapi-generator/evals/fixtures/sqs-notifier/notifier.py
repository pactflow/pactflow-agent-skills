import json, os
import boto3

sqs = boto3.client("sqs")
sns = boto3.client("sns")
QUEUE_URL = os.environ["EMAIL_QUEUE_URL"]  # https://sqs.eu-west-1.amazonaws.com/123/email-requests
TOPIC_ARN = os.environ["SENT_TOPIC_ARN"]


def poll():
    resp = sqs.receive_message(QueueUrl=QUEUE_URL, MaxNumberOfMessages=10)
    for m in resp.get("Messages", []):
        body = json.loads(m["Body"])
        send_email(body["to"], body["subject"], body.get("template", "default"))
        sns.publish(
            TopicArn=TOPIC_ARN,
            Message=json.dumps({"to": body["to"], "status": "sent", "attempts": 1}),
            MessageAttributes={"eventType": {"DataType": "String", "StringValue": "email.sent"}},
        )


def send_email(to, subject, template):
    ...
