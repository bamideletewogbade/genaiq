from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from google.cloud import storage
import os
import time

app = Flask(__name__)

# Define the directory to save uploaded files temporarily
UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'jpg', 'jpeg', 'png', 'docx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    """Check if the file is of an allowed type."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_to_gcs(file_path, bucket_name, destination_blob_name):
    """Uploads a file to Google Cloud Storage."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)

        blob.upload_from_filename(file_path)
        print(f"File {file_path} uploaded to {destination_blob_name}.")
    except Exception as e:
        print(f"Error uploading to GCS: {e}")

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handles file upload and upload to GCS."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        # Save the file temporarily
        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        filename = f"{filename}_{timestamp}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Define the GCS bucket and "folder" path
        bucket_name = 'genaiq_cloudbuild'
        folder_name = 'uploads/'  # Folder in GCS
        destination_blob_name = f'{folder_name}{filename}'
        
        # Upload the file to GCS
        upload_to_gcs(file_path, bucket_name, destination_blob_name)

        # Clean up the temporary file
        os.remove(file_path)

        return jsonify({
            "message": f"File '{filename}' uploaded to GCS bucket '{bucket_name}' in folder '{folder_name}' successfully!",
            "file_path": file_path
        }), 200
    else:
        return jsonify({"error": "File type not allowed"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
