from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
from ai_service import process_file  
from ai_service import upload_local_file_to_gcs

app = Flask(__name__)

# Set the upload folder
UPLOAD_FOLDER = 'temp_uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def ensure_folder_exists(folder_path):
    """Ensure the folder exists, create it if not."""
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

# Ensure the upload directory exists
ensure_folder_exists(app.config['UPLOAD_FOLDER'])

# Define allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_resume_page')
def upload_resume_page():
    return render_template('upload_resume_index.html')

@app.route('/upload_resume', methods=['POST'])
def upload_resume():
    # Ensure 'resume' is in the request files
    if 'resume' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['resume']
    
    # Check if the file is selected and has an allowed extension
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Ensure the folder exists
        ensure_folder_exists(os.path.dirname(file_path))

        # Save file locally
        file.save(file_path)

        # Upload file to GCS
        bucket_name = 'genaiq_cloudbuild'
        destination_blob_name = f'uploads/{filename}'

        # Upload file to GCS
        file_uri = upload_local_file_to_gcs(file_path, bucket_name, destination_blob_name)
        
        if file_uri:
            # Process file using GCS URI
            #analysis_result = process_file(file_uri)
            return render_template('tools.html'), 200
        else:
            return jsonify({'error': 'Failed to upload file to GCS'}), 500
    return jsonify({'error': 'Invalid file format'}), 400

@app.route('/tools')
def tools():
    return render_template('tool_selection_page.html')

@app.route('/get_feedback_page')
def get_feedback_page():
    return render_template('get_feedback_page.html')

if __name__ == "__main__":
    app.run(debug=True)
