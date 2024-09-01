import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.cloud import storage
from PyPDF2 import PdfReader
import docx
from io import BytesIO
import os
import logging
import pdfkit
import json
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def initialize_vertex_ai(project_id, location):
    """Initializes the Vertex AI environment."""
    try:
        vertexai.init(project=project_id, location=location)
        logging.info("Vertex AI initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize Vertex AI: {e}")
        raise

def download_file_from_gcs(file_uri):
    """Downloads a file from Google Cloud Storage."""
    try:
        storage_client = storage.Client()
        bucket_name, blob_name = file_uri.replace("gs://", "").split("/", 1)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        file_content = blob.download_as_bytes()
        logging.info(f"File downloaded successfully from GCS: {file_uri}")
        return file_content
    except Exception as e:
        logging.error(f"Error downloading from GCS: {e}")
        return None

def upload_local_file_to_gcs(file_path, bucket_name, destination_blob_name):
    """Uploads a local file to Google Cloud Storage."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(file_path)
        logging.info(f"File uploaded successfully to GCS: {destination_blob_name}")
        return f"gs://{bucket_name}/{destination_blob_name}"
    except Exception as e:
        logging.error(f"Error uploading to GCS: {e}")
        return None

def extract_text_from_pdf(file_content):
    """Extracts text from a PDF file."""
    try:
        with BytesIO(file_content) as file:
            reader = PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
        logging.info("Text extracted successfully from PDF.")
        return text
    except Exception as e:
        logging.error(f"Error extracting text from PDF: {e}")
        return ""

def extract_text_from_docx(file_content):
    """Extracts text from a DOCX file."""
    try:
        with BytesIO(file_content) as file:
            doc = docx.Document(file)
            text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
        logging.info("Text extracted successfully from DOCX.")
        return text
    except Exception as e:
        logging.error(f"Error extracting text from DOCX: {e}")
        return ""

def extract_text_from_txt(file_content):
    """Extracts text from a TXT file."""
    try:
        text = file_content.decode('utf-8')
        logging.info("Text extracted successfully from TXT.")
        return text
    except Exception as e:
        logging.error(f"Error extracting text from TXT: {e}")
        return ""

def call_vertex_ai(file_uri):
    """Calls Vertex AI to analyze the extracted text and returns the analysis in JSON format."""
    file_content = download_file_from_gcs(file_uri)
    
    if not file_content:
        logging.error(f"Failed to download file from GCS: {file_uri}")
        return {"error": "Failed to download file from GCS."}
    
    file_extension = os.path.splitext(file_uri)[1].lower()
    
    if file_extension == '.pdf':
        file_text = extract_text_from_pdf(file_content)
    elif file_extension == '.docx':
        file_text = extract_text_from_docx(file_content)
    elif file_extension == '.txt':
        file_text = extract_text_from_txt(file_content)
    else:
        logging.warning(f"Unsupported file type: {file_extension}")
        return {"error": "Unsupported file type."}
    
    if not file_text.strip():
        logging.warning("No text extracted from the file.")
        return {"error": "No text extracted from the file."}
    
    try:
        logging.info("Initializing Vertex AI with the given project ID and location.")
        project_id = "genaiq-433814"
        location = "us-central1"
        vertexai.init(project=project_id, location=location)

        logging.info("Loading the Vertex AI generative model.")
        model = GenerativeModel("gemini-1.5-flash-001",
        generation_config={"response_mime_type": "application/json"}
        )

        logging.info("Preparing the prompt for Vertex AI.")
        prompt = (
            "You are an HR expert with extensive experience in evaluating resumes. "
            "Please review the following resume and provide detailed feedback on the candidate's qualifications, achievements, "
            "and potential for career growth. Highlight areas of strength and suggest improvements. Also, provide an ATS match percentage "
            "for each section of the resume. Structure the feedback with the following fields:\n\n"
            "1. 'overall_feedback': A summary of the overall quality of the resume.\n"
            "2. 'feedback_cards': A list of sections, each containing:\n"
            "   - 'title': The section title (e.g., Professional Experience, Skills and Technologies, etc.).\n"
            "   - 'description': Detailed feedback on the section.\n"
            "   - 'ats_match': An ATS match percentage for this section.\n"
            "   - 'recommendations': Suggestions for improvement.\n"
            "Return response in JSON format, also remember to be as human as possible. Tone and clarity. Also be personal by using the person's name."
        )

        logging.info("Creating a Part object from the extracted file text.")
        part = Part.from_text(file_text)

        logging.info("Sending the prompt to Vertex AI for content generation.")
        response = model.generate_content([part, prompt])
        
        
        if response and response.text:
            logging.info("Received response from Vertex AI.")
            response_text = response.text
            
            logging.debug(f"Raw response text: {response_text}")

            try:
                return json.loads(response.text.strip('```json').strip('```').strip())
            except json.JSONDecodeError as json_err:
                logging.error(f"Failed to parse JSON response: {json_err}")
                return {"error": "Failed to parse JSON response.", "raw_response": response_text}
        else:
            logging.warning("No response received from Vertex AI.")
            return {"error": "No response received from Vertex AI."}

    except Exception as e:
        logging.error(f"Error in call_vertex_ai: {e}")
        return {"error": f"Error processing the file: {str(e)}"}