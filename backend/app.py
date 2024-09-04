from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
import os
import logging
from logging.handlers import RotatingFileHandler
from ai_service import upload_local_file_to_gcs, call_vertex_ai

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = '/home/bishoptewogbade/genaiq/backend/static/uploads/temp_uploads'
LOG_FILE_PATH = '/home/bishoptewogbade/genaiq/backend/app.log'
SECRET_KEY = "bishop"

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = SECRET_KEY

# Replace with your Paystack secret key
PAYSTACK_SECRET_KEY = 'sk_test_your_secret_key'

def setup_logging():
    """Sets up logging with file rotation."""
    # Create a file handler for logging with rotation
    file_handler = RotatingFileHandler(LOG_FILE_PATH, maxBytes=10000000, backupCount=5)
    file_handler.setLevel(logging.INFO)

    # Create a formatter and set it for the handler
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    # Create a logger object
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)

# Call setup_logging to configure logging
setup_logging()

def ensure_folder_exists(folder_path):
    """Ensure the folder exists, create it if not."""
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        app.logger.info(f"Created directory: {folder_path}")

# Ensure the upload directory exists
ensure_folder_exists(app.config['UPLOAD_FOLDER'])

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}

def allowed_file(filename):
    """Check if the file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    app.logger.info("Rendering index page")
    return render_template('index.html')

@app.route('/upload_resume_page')
def upload_resume_page():
    app.logger.info("Rendering upload resume page")
    return render_template('upload_resume_index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    app.logger.info("Received a file upload request")
    
    if 'resume' not in request.files:
        app.logger.warning("No file part in request")
        return jsonify({'error': 'No file part'}), 400

    file = request.files['resume']
    if file.filename == '':
        app.logger.warning("No selected file")
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        app.logger.info(f"File {filename} saved to {filepath}")

        try:
            # Upload file to GCS
            bucket_name = 'genaiq_cloudbuild'
            destination_blob_name = f'uploads/{filename}'
            file_uri = upload_local_file_to_gcs(filepath, bucket_name, destination_blob_name)
            app.logger.info(f"File URI: {file_uri}")

            # Store filename and file URI in session
            session['filename'] = filename
            session['file_uri'] = file_uri
            app.logger.info(f"Session data after upload: {session}")

            # Determine file type and prepare response
            file_type = file.mimetype.split('/')[1]
            response = {'success': True, 'file_type': file_type}

            if file_type == 'pdf':
                response['file_url'] = filepath
                app.logger.info("File type is PDF")
            elif file_type == 'plain':
                with open(filepath, 'r') as f:
                    content = f.read()
                response['content'] = content
                app.logger.info("File type is TXT")
            elif file_type == 'vnd.openxmlformats-officedocument.wordprocessingml.document':
                response['file_url'] = filepath
                app.logger.info("File type is DOCX")
            else:
                app.logger.error("Unsupported file type")
                response = {'error': 'Unsupported file type'}

        except Exception as e:
            app.logger.error(f"Error processing file: {e}")
            response = {'error': 'File processing error'}

        finally:
            # Clean up the local file
            if os.path.exists(filepath):
                os.remove(filepath)
                app.logger.info(f"File {filename} removed from local storage")

        return jsonify(response), 200 if 'error' not in response else 400
    else:
        app.logger.error("File type not allowed")
        return jsonify({'error': 'File type not allowed'}), 400

@app.route('/get_feedback_page', methods=['POST'])
def get_feedback_page():
    app.logger.info("Received request to get feedback page")

    try:
        filename = session.get('filename')
        file_uri = session.get('file_uri')
        app.logger.info(f"Session data at feedback page: filename={filename}, file_uri={file_uri}")

        if not filename or not file_uri:
            app.logger.error("Required session data missing")
            return jsonify({'error': 'Session data missing'}), 400

        # Process the file using AI service
        app.logger.info("Calling AI service to process the file")

        try:
            feedback = call_vertex_ai(file_uri)
            app.logger.info(f"Analysis result: {feedback}")
            session['ai_response'] = feedback


            # Process the result and prepare feedback data dynamically
            analysis_result = feedback
            return redirect(url_for('feedback_summary'))

        except Exception as e:
            app.logger.error(f"Error calling AI service: {e}")
            return jsonify({'error': 'Error calling AI service'}), 500

    except Exception as e:
        app.logger.error(f"Error processing feedback: {e}")
        return jsonify({'error': 'Error processing feedback'}), 500

def call_vertex_ai_test():
    """Simulated response from AI service."""
    simulated_response = {
        'overall_feedback': 'Sample overall feedback from AI.',
        'feedback_cards': [
            {
                'title': 'Summary',
                'description': 'Sample description for Summary.',
                'ats_match': 80,
                'recommendations': [
                    'Recommendation 1 for Summary',
                    'Recommendation 2 for Summary'
                ]
            },
            {
                'title': 'Experience',
                'description': 'Sample description for Experience.',
                'recommendations': [
                    'Recommendation 1 for Experience',
                    'Recommendation 2 for Experience'
                ]
            },
            {
                'title': 'Education',
                'description': 'Sample description for Education.',
                'recommendations': [
                    'Recommendation 1 for Education',
                    'Recommendation 2 for Education'
                ]
            },
            {
                'title': 'Skills',
                'description': 'Sample description for Skills.',
                'recommendations': [
                    'Recommendation 1 for Skills',
                    'Recommendation 2 for Skills'
                ]
            },
        ]
    }
    return simulated_response

@app.route('/download_feedback_pdf')
def download_feedback_pdf():
    """Serve the feedback PDF for download."""
    pdf_filepath = session.get('pdf_filepath')
    if pdf_filepath and os.path.exists(pdf_filepath):
        app.logger.info(f"Serving PDF: {pdf_filepath}")
        return send_file(pdf_filepath, as_attachment=True)
    else:
        app.logger.error("PDF file not found")
        return jsonify({'error': 'PDF file not found'}), 404

# Endpoint to only display summary
@app.route('/feedback_summary', methods=['GET'])
def feedback_summary():
    # Assume the AI-generated response is stored in the session
    ai_response = session.get('ai_response', {})
    summary = ai_response.get('overall_feedback', 'Summary not available.')

    return render_template('feedback_summary.html', summary=summary)

@app.route('/full_report', methods=['GET'])
def full_report():
    app.logger.info("Received request to get feedback page")

    try:
        filename = session.get('filename')
        file_uri = session.get('file_uri')
        app.logger.info(f"Session data at feedback page: filename={filename}, file_uri={file_uri}")

        if not filename or not file_uri:
            app.logger.error("Required session data missing")
            return jsonify({'error': 'Session data missing'}), 400

        # Process the file using AI service
        app.logger.info("Calling AI service to process the file")

        try:
            feedback = call_vertex_ai(file_uri)
            app.logger.info(f"Analysis result: {feedback}")
            session['ai_response'] = feedback

            # Process the result and prepare feedback data dynamically
            analysis_result = feedback
            return render_template('feedback_page.html', feedback=analysis_result), 200

        except Exception as e:
            app.logger.error(f"Error calling AI service: {e}")
            return jsonify({'error': 'Error calling AI service'}), 500

    except Exception as e:
        app.logger.error(f"Error processing feedback: {e}")
        return jsonify({'error': 'Error processing feedback'}), 500

@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if request.method == 'POST':
        # Process payment here
        payment_successful = True  # Example placeholder for actual payment logic
        
        if payment_successful:
            return redirect(url_for('full_report'))

    return render_template('payment.html')

@app.route('/start_payment', methods=['POST'])
def start_payment():
    email = request.form.get('email')
    payment_method = request.form.get('payment-method')

    # Determine the amount based on the payment method
    if payment_method == 'card':
        amount = 1000  # Amount in kobo (10 dollars), Paystack expects the amount in the smallest currency unit
        currency = 'NGN'  # Use 'NGN' for Naira
    elif payment_method == 'mobile_money':
        amount = 16000  # Amount in GHS, Paystack expects the amount in the smallest currency unit
        currency = 'GHS'  # Use 'GHS' for Ghana Cedis
    else:
        return jsonify({'status': 'failed', 'message': 'Invalid payment method'}), 400

    # Initialize the payment
    url = 'https://api.paystack.co/transaction/initialize'
    PAYSTACK_SECRET_KEY = 'sk_test_d09c41f57e1897f4ae815c7da361ab9e2a780d93'
    headers = {
        'Authorization': f'Bearer {PAYSTACK_SECRET_KEY}',
        'Content-Type': 'application/json',
    }

    data = {
        'email': email,
        'amount': amount,
        'currency': currency,  # Set the currency based on the payment method
        'callback_url': url_for('verify_payment', _external=True)  # Set callback URL to verify payment after completion
    }

    response = requests.post(url, json=data, headers=headers)
    response_data = response.json()

    if response_data['status']:
        # Redirect user to the Paystack payment page
        return redirect(response_data['data']['authorization_url'])
    else:
        return jsonify({'status': 'failed', 'message': 'Payment initialization failed'}), 400

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    app.logger.info(f"Serving file {filename}")
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

@app.route('/tools')
def tools():
    app.logger.info("Rendering tools selection page")
    return render_template('tool_selection_page.html')

if __name__ == "__main__":
    app.logger.info("Starting Flask application")
    app.run(debug=True)
