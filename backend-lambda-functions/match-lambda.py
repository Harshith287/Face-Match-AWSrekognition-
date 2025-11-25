import json
import boto3
import uuid
import base64
from io import BytesIO
import os

s3 = boto3.client("s3")
rekognition = boto3.client("rekognition")

BUCKET=os.environ['BUCKET']
FOLDER=os.environ['FOLDER']
PICS=os.environ['PICS']

def generate_read_url(key):
    return s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': BUCKET, 'Key': key},
        ExpiresIn=3600
    )


def match_images(bucket_key):
    images = s3.list_objects_v2(Bucket=BUCKET)
    print("all_objects", images)

    all_objects = s3.list_objects_v2(Bucket=BUCKET).get("Contents", [])
    print("all_objects", all_objects)

    new_images = []
    other_images = []

    for obj in all_objects:
        if obj["Key"] == bucket_key:
            print(obj["Key"])
            new_images.append(obj["Key"])

    for obj in all_objects:
        key = obj["Key"]

        if key.endswith("/"):
            continue

        if key.startswith(PICS):
            other_images.append(key)

    print("new_images", new_images)
    print("other images", other_images)
    
    try:
        faces=rekognition.detect_faces(
            Image={"S3Object": {"Bucket": BUCKET, "Name": bucket_key}}
        )
        print("faces",faces)
        no_of_faces=len(faces['FaceDetails'])
        print(no_of_faces)
        if no_of_faces>1:
            return {"statusCode": 500,
             "body": json.dumps({"error": "Multiple faces detected"})}
        if no_of_faces==0:
            return{
                "statusCode":500,
                "body":json.dumps({"error":"No Face Detected"})
            }
    
        if not bucket_key:
            return {"statusCode": 500, 
            "body": json.dumps({"error": "Missing selfie key"})}

    except Exception as e:
        print(f"INVALID IMAGE (skipping): {key} — {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error in face detection"})}

    matches = []

    # Compare only valid images
    for source in new_images:
        for target in other_images:
            try:
                response = rekognition.compare_faces(
                    SourceImage={"S3Object": {"Bucket": BUCKET, "Name": source}},
                    TargetImage={"S3Object": {"Bucket": BUCKET, "Name": target}},
                    SimilarityThreshold=0
                )

                for match in response.get("FaceMatches", []):
                    matches.append({
                        "source": source,
                        "target": target,
                        "similarity": match["Similarity"]
                    })

            except Exception as e:
                print(f"Eror comparing {source} <-> {target}: {e}")

    for rec in matches:
        print(rec)

    # ---- GROUP BY IMAGE WITH HIGHEST SCORE ----
    final_results = {}

    for m in matches:
        target = m["target"]
        sim = m["similarity"]

        if target not in final_results or sim > final_results[target]:
            final_results[target] = sim

    # ---- FILTER IMAGES WITH SIMILARITY > 80 ----
    filtered_matches = [
        {"image": img, "similarity": score}
        for img, score in final_results.items()
        if score >= 80
    ]

    filtered_matches.sort(key=lambda x: x["similarity"], reverse=True)
    print("filtered_matches", filtered_matches)
    
    if len(filtered_matches)==0:
        return{
            "statusCode":500,
            "body":json.dumps({"error": "Sorry,No Face  matched "})
        }

    return {
        "statusCode": 200,
        "body": json.dumps({
            "result_count": len(filtered_matches),
            # "matches": filtered_matches
            "matches": [
            {
                "image": m["image"],
                "similarity": m["similarity"],
                "imageUrl": generate_read_url(m["image"])
            }
            for m in filtered_matches
        ]
        })
    }

def lambda_handler(event, context):
    print(event)
    body = json.loads(event.get("body", "{}"))
    url=body.get('url')
    fields=body.get('fields')
    key=body.get('key')
    return match_images(key)
    # TODO implement
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
