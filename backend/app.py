from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
import os
import logging
from logging.handlers import RotatingFileHandler
from ai_service import upload_local_file_to_gcs, call_vertex_ai, roast_resume
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

def roast_resume_test():
    # This function would normally call the AI service.
    # For this example, we will return the static JSON response.
    return {
        "introduction": "Yo, yo, yo! Hold up, hold up, hold up! Is this a resume or a self-help book? 'Cause I'm getting more life advice than job qualifications here. This resume is so long, it's practically a novella. It's like a novel of 'How to Sound Like You Have a Life When You Don't.'",
        "First Impressions": {
            "header": "First Impressions",
            "description": "Okay, so the first thing I see is this picture. It's like they just grabbed a random stock photo of a dude with a generic smile. You know, the kind of smile you get when you're holding back a sneeze in a crowded elevator. And the summary? It's like a generic AI chatbot wrote it. 'Passionate software developer' - Yeah, we all are. We're passionate about not being hungry. This guy's gotta find a new passion, because this resume is giving 'passion project that's going nowhere.'"
        },
        "Section-by-Section Roast": {
            "header": "Section-by-Section Roast",
            "description": "Let's break down this thing, section by section, like a pro wrestler taking apart his opponent.\n\n**Experience: ** Okay, this is where it gets interesting. This guy's been at three jobs in three years, and they all have a similar theme: 'I did things and now I'm leaving.' This resume is like a series of breakup letters. 'Oh, I integrated Kafka, so I'm gone. See ya!' Dude, you're not a secret agent. You're a software developer. Get a grip!\n\n**Education: ** Catholic University College, Ghana. I'm not saying it's a bad school, but it sounds like a place you'd go if you wanted to major in 'How to Be a Humblebragger.'\n\n**Skills: ** This is where I start to lose my mind. We got 'Java, Python, Dart, SQL, PL/SQL, JavaScript...' Dude, you're trying to impress me with your knowledge, but all I see is a laundry list of buzzwords. This isn't a coding bootcamp, it's a resume! You gon' learn today!\n\n**Keywords: ** 'AI', 'Fintech', 'Mobile App Development.' This guy's throwing every trending keyword in there like he's trying to win the 'Most Generic Software Developer' award. You're not a Techie Superhero. You're just a guy who knows how to write some code. Calm down, bruh!"
        },
        "Kevin Hart-isms": {
            "header": "Kevin Hart-isms",
            "description": "This resume? It's like a car with a 'For Sale' sign on it, but the engine's missing. You're tellin' me you're a 'Consultant Programmer' but you're still working on 'Three Knights'? That's like me saying, 'I'm a comedian, but I'm still learning how to tell jokes.' And 'AI-driven solutions'? That's like saying, 'I'm a genius, I can solve problems.' We all can, man. We're humans. We're supposed to solve problems."
        },
        "Physical Comedy": {
            "header": "Physical Comedy",
            "description": "If I saw this resume in person, I'd be running around the room, arms flailing, screaming 'What is this?! What. Is. This?!' Then I'd stop, take a deep breath, and say, 'This resume is so bad, it's good.' Because it's so ridiculous, it's actually kind of entertaining. It's like a bad movie you can't stop watching."
        },
        "Real Talk": {
            "header": "Real Talk",
            "description": "Yo, listen up. I know you're trying to impress people with this resume, but all you're doing is making yourself look like a try-hard. Focus on your skills, your experience, and your achievements. Don't just throw keywords at the wall and see what sticks. Be authentic, be confident, and be yourself. You'll go farther in the long run."
        }
    }

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
