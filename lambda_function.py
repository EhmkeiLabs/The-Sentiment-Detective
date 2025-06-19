import boto3
import json
import uuid
import os

# Initialize AWS clients
s3 = boto3.client('s3')
bedrock_runtime = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')

# Get the table name from an environment variable
DYNAMODB_TABLE_NAME = os.environ['DYNAMODB_TABLE_NAME']
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

def lambda_handler(event, context):
    # 1. Get the uploaded file details from the S3 event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    try:
        # 2. Read the text content from the S3 object
        response = s3.get_object(Bucket=bucket, Key=key)
        review_text = response['Body'].read().decode('utf-8')

        # 3. Prepare the prompt for the Bedrock model
        prompt = f"""
        Human: You are an expert customer feedback analyst. Please analyze the following customer review.
        Provide your analysis in a structured JSON format with the following keys: "sentiment", "key_topics", and "urgency_level".

        - "sentiment" should be one of: POSITIVE, NEGATIVE, or NEUTRAL.
        - "key_topics" should be a list of the main subjects mentioned in the review.
        - "urgency_level" should be one of: HIGH, MEDIUM, or LOW, based on how urgently a response is needed.

        Here is the review:
        <review>
        {review_text}
        </review>

        Assistant:
        """

        # 4. Call the Bedrock API
        request_body = {
            "prompt": prompt,
            "max_tokens_to_sample": 500,
            "temperature": 0.1,
        }
        
        bedrock_response = bedrock_runtime.invoke_model(
            body=json.dumps(request_body),
            modelId="anthropic.claude-v2", # Make sure you have enabled this model
            accept="application/json",
            contentType="application/json"
        )
        
        # 5. Extract and parse the JSON response from the model
        response_body = json.loads(bedrock_response['body'].read())
        analysis_json_string = response_body['completion'].strip()
        analysis = json.loads(analysis_json_string)

        # 6. Store the results in DynamoDB
        review_id = str(uuid.uuid4()) # Generate a unique ID for the review
        
        table.put_item(
            Item={
                'review_id': review_id,
                'original_text': review_text,
                'sentiment': analysis.get('sentiment', 'UNKNOWN'),
                'key_topics': analysis.get('key_topics', []),
                'urgency_level': analysis.get('urgency_level', 'UNKNOWN')
            }
        )
        
        print(f"Successfully processed and stored analysis for {key}")
        return {'statusCode': 200, 'body': json.dumps('Analysis complete!')}

    except Exception as e:
        print(f"Error processing file {key}: {e}")
        raise e
