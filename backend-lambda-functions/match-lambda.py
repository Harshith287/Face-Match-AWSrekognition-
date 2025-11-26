import json
import boto3
import os

s3 = boto3.client("s3")
rekognition = boto3.client("rekognition")

BUCKET = os.environ["BUCKET"]
PICS = os.environ["PICS"]
COLLECTION_ID = "FaceCollection"  # any name you like
indexed_done = False

def ensure_collection():
    collections = rekognition.list_collections()["CollectionIds"]

    # Create if missing
    if COLLECTION_ID not in collections:
        rekognition.create_collection(CollectionId=COLLECTION_ID)

    # ---- Get existing indexed images ----
    indexed = set()
    paginator_faces = rekognition.get_paginator("list_faces")

    for page in paginator_faces.paginate(CollectionId=COLLECTION_ID):
        for face in page.get("Faces", []):
            indexed.add(face["ExternalImageId"])

    print("Already indexed:", len(indexed))

    # ---- Now check for new S3 images ----
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=BUCKET, Prefix=PICS):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue

            filename = os.path.basename(key).replace(" ", "_")

            if filename in indexed:
                # print(filename, "already exists. Skipping.")
                continue

            # print("Indexing:", filename)

            try:
                resp = rekognition.index_faces(
                    CollectionId=COLLECTION_ID,
                    Image={"S3Object": {"Bucket": BUCKET, "Name": key}},
                    ExternalImageId=filename
                )
                # print("Indexed faces:", len(resp["FaceRecords"]))
            except Exception as e:
                print("Failed:", key, e)


def generate_read_url(key):
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=3600
    )


def match_images(bucket_key):

    # STEP-1: ensure collection & pics are indexed
    # ensure_collection()
    
    print(bucket_key)

    # STEP-2: validate selfie
    faces = rekognition.detect_faces(
        Image={"S3Object": {"Bucket": BUCKET, "Name": bucket_key}}
    )
    count = len(faces['FaceDetails'])
    
    if count != 1:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Image must contain exactly 1 face"})
        }

    # STEP-3: only one call now
    response = rekognition.search_faces_by_image(
        CollectionId=COLLECTION_ID,
        Image={"S3Object": {"Bucket": BUCKET, "Name": bucket_key}},
        FaceMatchThreshold=80,
        MaxFaces=1000
    )
    # print("response",response)
    

    matches = response.get("FaceMatches", [])
    if not matches:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "No matching face found"})
        }

    results = []
    # for m in matches:
    #     print(m)
    for m in matches:
        key = m["Face"]["ExternalImageId"]
        sim = m["Similarity"]
        full_key = f"{PICS}{key}"
        # print(PICS)
        # print(full_key)


        results.append({
            "image": full_key,
            "similarity": sim,
            "imageUrl": generate_read_url(full_key)
        })

    results.sort(key=lambda x: x["similarity"], reverse=True)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "count": len(results),
            "matches": results
        })
    }


def lambda_handler(event, context):
    body = json.loads(event.get("body", "{}"))
    key = body.get("key")
    print("Selfie:", key)
    

    return match_images(key)