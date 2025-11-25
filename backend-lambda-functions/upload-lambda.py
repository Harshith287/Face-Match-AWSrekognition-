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


def upload_image(filename, content_type):
    try:
        if not filename or not content_type:
            return response(400, {"error": "filename and contentType required"})

        # Create unique S3 key
        unique_key = f"{FOLDER}{filename}"

        # Build presigned POST config
        presigned_post = s3.generate_presigned_post(
            Bucket=BUCKET,
            Key=unique_key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["starts-with", "$Content-Type", "image/"],
                #  ["eq", "$x-amz-server-side-encryption", "aws:kms"],
                ["content-length-range", 1, 10 * 1024 * 1024]
            ],
            
            ExpiresIn=1000
        )

        print("presigned", presigned_post)

        return {
            "url": presigned_post["url"],
            "fields": presigned_post["fields"],
            "key": unique_key
        }

    except Exception as e:
        print("ERROR:", e)


def is_valid_image(bucket, key):
    """
    This checks if the image is real JPEG or PNG by trying Rekognition.
    If DetectFaces works, the image is valid.
    """
    try:
        rekognition.detect_faces(
            Image={"S3Object": {"Bucket": bucket, "Name": key}}
        )
        return True

    except Exception as e:
        print(f"INVALID IMAGE (skipping): {key} — {e}")
        return False


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
                print(f"Error comparing {source} <-> {target}: {e}")

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

    return {
        "statusCode": 200,
        "body": json.dumps({
            "result_count": len(filtered_matches),
            "matches": filtered_matches
        })
    }


def lambda_handler(event, context):
    body = json.loads(event.get("body", "{}"))
    print("event", event)

    filename = body.get("filename")
    content_type = body.get("contentType")

    unique_key = f"{FOLDER}{filename}"

    # BUG FIX NOTE: your original code used undefined variable "content"
    presigned = upload_image(filename, content_type)

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(presigned)
    }

    return match_images(unique_key)


def response_upload(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }