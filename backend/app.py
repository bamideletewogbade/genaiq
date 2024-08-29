from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
import logging
import webbrowser
from ai_service import process_file, upload_local_file_to_gcs

# Configure logging
logging.basicConfig(
    filename='app.log',  # Log file name
    level=logging.DEBUG,  # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Log format
    datefmt='%Y-%m-%d %H:%M:%S'  # Date format
)

logger = logging.getLogger(__name__)
logger.info("Logging is set up.")

app = Flask(__name__)

# Set the upload folder
UPLOAD_FOLDER = 'temp_uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def ensure_folder_exists(folder_path):
    """Ensure the folder exists, create it if not."""
    if not os.path.exists(folder_path):
        logger.debug(f"Creating directory at {folder_path}")
        os.makedirs(folder_path)
    else:
        logger.debug(f"Directory already exists at {folder_path}")

# Ensure the upload directory exists
ensure_folder_exists(app.config['UPLOAD_FOLDER'])

# Define allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_resume_page')
def upload_resume_page():
    return render_template('upload_resume_index.html')

@app.route('/save_file_to_gcs', methods=['POST'])
def save_file_to_gcs():
    """Endpoint to save file to Google Cloud Storage."""
    if 'resume' not in request.files:
        logger.error("No file part in request")
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['resume']

    if file.filename == '':
        logger.error("No file selected for upload")
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        ensure_folder_exists(os.path.dirname(file_path))

        try:
            # Save file locally
            file.save(file_path)
            logger.info(f"File saved locally at {file_path}")

            # Upload file to GCS
            bucket_name = 'genaiq_cloudbuild'
            destination_blob_name = f'uploads/{filename}'
            file_uri = upload_local_file_to_gcs(file_path, bucket_name, destination_blob_name)

            if file_uri:
                logger.info(f"File uploaded to GCS at {file_uri}")
                return jsonify({'file_uri': file_uri}), 200
            else:
                logger.error("Failed to upload file to GCS")
                return jsonify({'error': 'Failed to upload file to GCS'}), 500
        except Exception as e:
            logger.error(f"Exception during file upload: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Local file {file_path} removed after processing.")
    else:
        logger.error("Invalid file format")
        return jsonify({'error': 'Invalid file format'}), 400

@app.route('/upload_resume', methods=['POST'])
def upload_resume():
    """Endpoint to upload resume and process it."""
    logger.info("Received request to /upload_resume")
    logger.debug(f"Request files: {request.files}")
    logger.debug(f"Request form: {request.form}")
    if 'resume' not in request.files:
        logger.error("No file part in request")
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['resume']
    
    
    if file.filename == '':
        logger.error("No file selected for upload")
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        logger.info(f"Received file: {file.filename}")
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        ensure_folder_exists(os.path.dirname(file_path))

        try:
            # Save file locally
            file.save(file_path)
            logger.info(f"File saved locally at {file_path}")

            # Upload file to GCS
            bucket_name = 'genaiq_storage'
            destination_blob_name = f'uploads/{filename}'
            file_uri = upload_local_file_to_gcs(file_path, bucket_name, destination_blob_name)

            if file_uri:
                logger.info(f"File uploaded to GCS at {file_uri}")
                # Process the file using AI service
                analysis_result = process_file(file_uri)
                logger.info("Feedback generated successfully")

                # Render feedback page with analysis result
                return render_template('get_feedback_page.html')
            else:
                logger.error("Failed to upload file to GCS")
                return jsonify({'error': 'Failed to upload file to GCS'}), 500

        except Exception as e:
            logger.error(f"Exception during feedback page generation: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Local file {file_path} removed after processing.")
    else:
        logger.error("Invalid file format")
        return jsonify({'error': 'Invalid file format'}), 400

@app.route('/tools')
def tools():
    return render_template('tool_selection_page.html')

if __name__ == "__main__":
     # Get the local server URL
    url = "http://127.0.0.1:5000/"
    
    # Open the default web browser
    webbrowser.open_new(url)
    
    # Run the Flask app
    app.run(debug=True)
