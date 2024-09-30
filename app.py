from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
import os
import logging
from logging.handlers import RotatingFileHandler
from ai_service import upload_local_file_to_gcs, call_vertex_ai, roast_resume, match_resume_to_job
import requests

app = Flask(__name__)

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'temp_uploads')
LOG_FILE_PATH = os.path.join(BASE_DIR, 'app.log')
SECRET_KEY = "bishop"

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = SECRET_KEY

# Replace with your Paystack secret key
PAYSTACK_SECRET_KEY = 'sk_test_febcf78bd1f309332ea2a8dbfd8aa366895d97fe'
PAYSTACK_PUBLIC_KEY = 'pk_test_231e69ddcb26e40256da24ec7ebc279395c5c4c1'


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
            bucket_name = 'genaiq_storage_new'
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

# @app.route('/get_feedback_page', methods=['POST'])
# def get_feedback_page():
#     app.logger.info("Received request to get feedback page")

#     try:
#         filename = session.get('filename')
#         file_uri = session.get('file_uri')
#         app.logger.info(f"Session data at feedback page: filename={filename}, file_uri={file_uri}")

#         if not filename or not file_uri:
#             app.logger.error("Required session data missing")
#             return jsonify({'error': 'Session data missing'}), 400

#         # Process the file using AI service
#         app.logger.info("Calling AI service to process the file")

#         try:
#             feedback = call_vertex_ai(file_uri)
#             app.logger.info(f"Analysis result: {feedback}")
#             session['ai_response'] = feedback


#             # Process the result and prepare feedback data dynamically
#             analysis_result = feedback
#             return render_template('full_report.html', feedback=analysis_result), 200

#         except Exception as e:
#             app.logger.error(f"Error calling AI service: {e}")
#             return jsonify({'error': 'Error calling AI service'}), 500

#     except Exception as e:
#         app.logger.error(f"Error processing feedback: {e}")
#         return jsonify({'error': 'Error processing feedback'}), 500


# Endpoint to only display summary
@app.route('/feedback_summary', methods=['POST', 'GET'])
def feedback_summary():
    app.logger.info("Received request to get feedback summary page")

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

            ai_response = session.get('ai_response')
    
            summary = ai_response.get('overall_feedback', 'Summary not available.')
            return render_template('feedback_summary.html', summary=summary), 200

        except Exception as e:
            app.logger.error(f"Error calling AI service: {e}")
            return jsonify({'error': 'Error calling AI service'}), 500

    except Exception as e:
        app.logger.error(f"Error processing feedback: {e}")
        return jsonify({'error': 'Error processing feedback'}), 500
  
@app.route('/full_report', methods=['POST','GET'])
def full_report():
    app.logger.info("Received request to get feedback full report page")

    try:
        # filename = session.get('filename')
        # file_uri = session.get('file_uri')
        # app.logger.info(f"Session data at feedback page: filename={filename}, file_uri={file_uri}")

        # if not filename or not file_uri:
        #     app.logger.error("Required session data missing")
        #     return jsonify({'error': 'Session data missing'}), 400

        # # Process the file using AI service
        # app.logger.info("Calling AI service to process the file")

        try:
            # feedback = call_vertex_ai(file_uri)
            # app.logger.info(f"Analysis result: {feedback}")
            ai_response = session.get('ai_response')

            # Process the result and prepare feedback data dynamically
            analysis_result = ai_response
            return render_template('full_report.html', feedback=analysis_result), 200

        except Exception as e:
            app.logger.error(f"Error calling AI service: {e}")
            return jsonify({'error': 'Error calling AI service'}), 500

    except Exception as e:
        app.logger.error(f"Error processing feedback: {e}")
        return jsonify({'error': 'Error processing feedback'}), 500

@app.route('/roast')
def resume_roast():
    return render_template('resume_roast.html')

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

@app.route('/match_jd')
def match_jd():
    return render_template('jd_matcher.html')


@app.route('/match', methods=['POST'])
def match():
    try:
        # Check if both resume and job description are provided
        if 'resume' not in request.files or 'job_description' not in request.form:
            app.logger.error("No resume or job description provided.")
            return jsonify({"error": "No resume or job description provided."}), 400

        resume = request.files['resume']
        job_description = request.form['job_description']

        # Check if a valid file is uploaded
        if resume.filename == '' or not allowed_file(resume.filename):
            app.logger.error("Invalid file type or no file selected.")
            return jsonify({"error": "Invalid file type or no file selected."}), 400

        # Save the uploaded resume
        filename = secure_filename(resume.filename)
        resume_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        resume.save(resume_path)
        app.logger.info(f"Resume uploaded and saved at {resume_path}")

        # Process the resume file
        try:
            bucket_name = 'genaiq_storage_new'
            destination_blob_name = f'uploads/{filename}'
            file_uri = upload_local_file_to_gcs(resume_path, bucket_name, destination_blob_name)
            app.logger.info(f"File URI: {file_uri}")

            # Store session data
            session['job_description'] = job_description
            session['file_uri'] = file_uri
            app.logger.info(f"Session data after upload: {session}")

            result = match_resume_to_job(file_uri, job_description)
            app.logger.info(f"AI Response: {result}")

            os.remove(resume_path)  # Clean up uploaded file after processing
            app.logger.info(f"Deleted resume file: {resume_path}")

            return render_template('jd_matcher_result.html', result=result)
        except Exception as e:
            app.logger.error(f"Error processing file: {e}")
            return jsonify({"error": "File processing error"}), 500
    except Exception as e:
        app.logger.error(f"Error in match function: {e}")
        return jsonify({"error": "An error occurred during processing."}), 500

@app.route('/payment')
def payment():
    app.logger.info("Rendering payment page")
    return render_template('paymentform.html')

@app.route('/start_payment', methods=['POST'])
def start_payment():
    email = request.form.get('email')
    payment_method = request.form.get('payment-method')

    app.logger.info(f"Received start_payment request with email: {email} and payment_method: {payment_method}")

    if not email:
        app.logger.error('Email not provided')
        return jsonify({'status': 'failed', 'message': 'Email is required'}), 400

    if payment_method not in ['card', 'mobile_money']:
        app.logger.error('Invalid payment method: %s', payment_method)
        return jsonify({'status': 'failed', 'message': 'Invalid payment method'}), 400

    amount = 700 
    currency = 'NGN'  

    url = 'https://api.paystack.co/transaction/initialize'
    headers = {
        'Authorization': f'Bearer {PAYSTACK_SECRET_KEY}',
        'Content-Type': 'application/json',
    }

    data = {
        'email': email,
        'amount': int(float(amount) * 100),
        'currency': currency,
        'callback_url': url_for('verify_payment', _external=True)
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response_data = response.json()

        app.logger.info(f"Paystack response: {response_data}")

        if response_data['status']:
            return jsonify({
                'status': 'success',
                'authorization_url': response_data['data']['authorization_url']
            })
        else:
            return jsonify({
                'status': 'failed',
                'message': response_data.get('message', 'Payment initialization failed')
            }), 400

    except requests.exceptions.RequestException as e:
        app.logger.error('Request to Paystack failed: %s', e)
        return jsonify({
            'status': 'failed',
            'message': 'Payment initialization failed'
        }), 500

@app.route('/verify_payment')
def verify_payment():
    reference = request.args.get('reference')

    if not reference:
        return jsonify({'status': 'failed', 'message': 'No reference provided'}), 400

    url = f'https://api.paystack.co/transaction/verify/{reference}'
    headers = {'Authorization': f'Bearer {PAYSTACK_SECRET_KEY}'}

    try:
        response = requests.get(url, headers=headers)
        response_data = response.json()

        if response_data['status']:
            # Payment was successful
            feedback = session.get('ai_response')      
        if not feedback:
            feedback = "No feedback available"
            session['feedback'] = feedback
            return redirect(url_for('full_report'))
        else:
            return jsonify({
                'status': 'failed',
                'message': 'Payment verification failed'
            }), 400

    except requests.exceptions.RequestException as e:
        app.logger.error('Request to Paystack failed: %s', e)
        return jsonify({
            'status': 'failed',
            'message': 'Payment verification failed'
        }), 500


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    app.logger.info(f"Serving file {filename}")
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

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

if __name__ == "__main__":
    app.logger.info("Starting Flask application")
    app.run(debug=True, host='0.0.0.0', port=8080)
