from flask import Flask, render_template, request, jsonify, send_file, session
from werkzeug.utils import secure_filename
import os
import logging
from ai_service import process_file, upload_local_file_to_gcs

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'temp_uploads/')
LOG_FILE_PATH = os.getenv('LOG_FILE_PATH', '/home/bamidele_tewogbade1/genaiq/backend/app.log')
SECRET_KEY = "bishop"

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = SECRET_KEY

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(LOG_FILE_PATH),
                              logging.StreamHandler()])

logger = logging.getLogger(__name__)

def ensure_folder_exists(folder_path):
    """Ensure the folder exists, create it if not."""
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        logger.info(f"Created directory: {folder_path}")

# Ensure the upload directory exists
ensure_folder_exists(app.config['UPLOAD_FOLDER'])

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    logger.info("Rendering index page")
    return render_template('index.html')

@app.route('/upload_resume_page')
def upload_resume_page():
    logger.info("Rendering upload resume page")
    return render_template('upload_resume_index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    logger.info("Received a file upload request")
    
    if 'resume' not in request.files:
        logger.warning("No file part in request")
        return jsonify({'error': 'No file part'}), 400

    file = request.files['resume']
    if file.filename == '':
        logger.warning("No selected file")
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        logger.info(f"File {filename} saved to {filepath}")

        try:
            # Upload file to GCS
            bucket_name = 'genaiq_storage'
            destination_blob_name = f'uploads/{filename}'
            file_uri = upload_local_file_to_gcs(filepath, bucket_name, destination_blob_name)
            logger.info(f"File URI: {file_uri}")

            # Store filename and file URI in session
            session['filename'] = filename
            session['file_uri'] = file_uri
            logger.info(f"Session data after upload: {session}")

            # Determine file type and prepare response
            if file.mimetype == 'application/pdf':
                logger.info(f"File type is PDF")
                response = {'success': True, 'file_type': 'pdf', 'file_url': filepath}
            elif file.mimetype == 'text/plain':
                with open(filepath, 'r') as f:
                    content = f.read()
                logger.info("File type is TXT")
                response = {'success': True, 'file_type': 'txt', 'content': content}
            elif file.mimetype == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                logger.info("File type is DOCX")
                response = {'success': True, 'file_type': 'docx', 'file_url': filepath}
            else:
                logger.error("Unsupported file type")
                response = {'error': 'Unsupported file type'}

        except Exception as e:
            logger.error(f"Error processing file: {e}")
            response = {'error': 'File processing error'}

        finally:
            # Clean up the local file
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"File {filename} removed from local storage")

        return jsonify(response), 200 if 'error' not in response else 400
    else:
        logger.error("File type not allowed")
        return jsonify({'error': 'File type not allowed'}), 400

@app.route('/get_feedback_page', methods=['POST'])
def get_feedback_page():
    logger.info("Received request to get feedback page")

    try:
        filename = session.get('filename')
        file_uri = session.get('file_uri')
        logger.info(f"Session data at feedback page: {filename} + {file_uri}")

        if not filename or not file_uri:
            logger.error("Required session data missing")
            return jsonify({'error': 'Session data missing'}), 400

        # Process the file using AI service
        analysis_result = process_file(file_uri)
        logger.info("Analysis completed successfully")
        return render_template('feedback_page.html', analysis_result=analysis_result), 200

    except Exception as e:
        logger.error(f"Error in feedback page: {e}")
        return jsonify({'error': 'Error processing feedback'}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    logger.info(f"Serving file {filename}")
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

@app.route('/tools')
def tools():
    logger.info("Rendering tools selection page")
    return render_template('tool_selection_page.html')

if __name__ == "__main__":
    logger.info("Starting Flask application")
    app.run(debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true')
