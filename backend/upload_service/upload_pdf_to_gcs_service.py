from google.cloud import storage

def upload_to_gcs(file_path, bucket_name, destination_blob_name):
    """Uploads a file to Google Cloud Storage."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(file_path)
    print(f"File {file_path} uploaded to {destination_blob_name}.")
