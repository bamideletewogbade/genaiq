import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.cloud import storage
from PyPDF2 import PdfReader
import docx
from io import BytesIO
import os
import logging

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

def process_file(file_uri):
    """Processes the file by extracting text and sending it to Vertex AI for analysis."""
    file_content = download_file_from_gcs(file_uri)
    
    if file_content:
        file_extension = os.path.splitext(file_uri)[1].lower()
        
        if file_extension == '.pdf':
            file_text = extract_text_from_pdf(file_content)
        elif file_extension == '.docx':
            file_text = extract_text_from_docx(file_content)
        elif file_extension == '.txt':
            file_text = extract_text_from_txt(file_content)
        else:
            logging.warning(f"Unsupported file type: {file_extension}")
            return "Unsupported file type."

        if file_text.strip():
            result = call_vertex_ai(file_text)
            return result
        else:
            logging.warning("No text extracted from the file.")
            return "No text extracted from the file."
    else:
        logging.error("Failed to download file from GCS.")
        return "Failed to download file from GCS."

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

def call_vertex_ai(file_text):
    """Calls Vertex AI to analyze the extracted text."""
    try:
        project_id = "genaiq-433814"
        location = "us-central1"
        initialize_vertex_ai(project_id, location)

        model = GenerativeModel("gemini-1.5-flash-001")

        prompt = (
            "As an HR expert with extensive experience, please review the following CV and provide detailed feedback "
            "on how well it showcases the candidate's qualifications, achievements, and overall potential for career growth. "
            "Highlight areas of strength and suggest improvements where applicable.\n\n Try and get personal by using personal information such as name to refer to user"
            "<h3>Overall Feedback</h3>"
            "<p>{{ analysis_result.overall }}</p>"
            "<h3>Content</h3>"
            "<p>{{ analysis_result.content }}</p>"
            "<h3>Structure</h3>"
            "<p>{{ analysis_result.structure }}</p>"
            "<h3>Formatting</h3>"
            "<p>{{ analysis_result.formatting }}</p>"
            "<h3>Language</h3>"
            "<p>{{ analysis_result.language }}</p>"
        )

        part = Part.from_text(file_text)
        response = model.generate_content([part, prompt])
        logging.info("Vertex AI call successful.")
        print(response.text)
        return response.text
    except Exception as e:
        logging.error(f"Error calling Vertex AI: {e}")
        return "Error processing the file."

