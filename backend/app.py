from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
import os
import logging
from logging.handlers import RotatingFileHandler
from ai_service import upload_local_file_to_gcs, call_vertex_ai, roast_resume, match_resume_with_jd
import requests

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = '/home/bishoptewogbade/genaiq/backend/static/uploads/temp_uploads'
LOG_FILE_PATH = '/home/bishoptewogbade/genaiq/backend/app.log'
SECRET_KEY = "bishop"

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = SECRET_KEY

# Replace with your Paystack secret key
PAYSTACK_SECRET_KEY = 'sk_test_d09c41f57e1897f4ae815c7da361ab9e2a780d93'

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
            return render_template('full_report.html', feedback=analysis_result), 200

        except Exception as e:
            app.logger.error(f"Error calling AI service: {e}")
            return jsonify({'error': 'Error calling AI service'}), 500

    except Exception as e:
        app.logger.error(f"Error processing feedback: {e}")
        return jsonify({'error': 'Error processing feedback'}), 500

@app.route('/get_roast_page', methods=['POST'])
def roast_resume_page():
    app.logger.info("Received request to get roast page")

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
            roast = roast_resume(file_uri)
            app.logger.info(f"Analysis result: {roast}")
            session['ai_roast_response'] = roast


            # # Process the result and prepare feedback data dynamically
            # analysis_result = roast
            return render_template('roast_response.html', roast=roast), 200

        except Exception as e:
            app.logger.error(f"Error calling AI service: {e}")
            return jsonify({'error': 'Error calling AI service'}), 500

    except Exception as e:
        app.logger.error(f"Error processing feedback: {e}")
        return jsonify({'error': 'Error processing feedback'}), 500

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

    # Log received request data
    app.logger.info(f"Received start_payment request with email: {email} and payment_method: {payment_method}")

    if not email:
        app.logger.error('Email not provided')
        return jsonify({'status': 'failed', 'message': 'Email is required'}), 400

    if payment_method not in ['card', 'mobile_money']:
        app.logger.error('Invalid payment method: %s', payment_method)
        return jsonify({'status': 'failed', 'message': 'Invalid payment method'}), 400


    amount = 160 * 100
    currency = 'GHS'

    # Initialize the payment
    url = 'https://api.paystack.co/transaction/initialize'
    headers = {
        'Authorization': f'Bearer {PAYSTACK_SECRET_KEY}',
        'Content-Type': 'application/json',
    }

    data = {
        'email': email,
        'amount': amount,
        'currency': currency,
        'callback_url': url_for('verify_payment', _external=True)
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        # response.raise_for_status()  # Raise an HTTPError for bad responses
        response_data = response.json()

        # Log Paystack response data
        app.logger.info(f"Paystack response: {response_data}")

        if response_data['status']:
            app.logger.info('Payment initialization successful. Redirecting to %s', response_data['data']['authorization_url'])
            return redirect(response_data['data']['authorization_url'])
        else:
            app.logger.error('Payment initialization failed: %s', response_data.get('message', 'Unknown error'))
            return jsonify({'status': 'failed', 'message': 'Payment initialization failed'}), 400

    except requests.exceptions.RequestException as e:
        app.logger.error('Request to Paystack failed: %s', e)
        return jsonify({'status': 'failed', 'message': 'Payment initialization failed'}), 500


@app.route('/verify_payment', methods=['GET'])
def verify_payment():
    reference = request.args.get('reference')

    app.logger.info(f"Received verify_payment request with reference: {reference}")

    if not reference:
        app.logger.error('Reference not provided')
        return jsonify({'status': 'failed', 'message': 'Reference not provided'}), 400

    # Verify the payment with Paystack
    url = f'https://api.paystack.co/transaction/verify/{reference}'
    headers = {
        'Authorization': f'Bearer {PAYSTACK_SECRET_KEY}',
        'Content-Type': 'application/json',
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        response_data = response.json()

        # Log Paystack response data
        app.logger.info(f"Paystack verification response: {response_data}")

        if response_data['status']:
            payment_status = response_data['data']['status']
            if payment_status == 'success':
                app.logger.info('Payment successful for reference %s', reference)
                return jsonify({'status': 'success', 'message': 'Payment successful'}), 200
            else:
                app.logger.error('Payment failed for reference %s', reference)
                return jsonify({'status': 'failed', 'message': 'Payment failed'}), 400
        else:
            app.logger.error('Payment verification failed for reference %s: %s', reference, response_data.get('message', 'Unknown error'))
            return jsonify({'status': 'failed', 'message': 'Payment verification failed'}), 400

    except requests.exceptions.RequestException as e:
        app.logger.error('Request to Paystack failed: %s', e)
        return jsonify({'status': 'failed', 'message': 'Payment verification failed'}), 500

@app.route('/match', methods=['POST'])
def match():
    resume = request.files['resume']
    job_description = request.form['job_description']
    
    if resume and job_description:
        filename = secure_filename(resume.filename)
        resume.save(filename)
        
        # Process the resume and job description using your AI model
        result = match_resume_with_jd(filename, job_description)
        
        return render_template('jd_matcher.html', result=result)
    else:
        return render_template('jd_matcher.html', result=None)

@app.route('/roast')
def resume_roast():

    return render_template('resume_roast.html')

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
