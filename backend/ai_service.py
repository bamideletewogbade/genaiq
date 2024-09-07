import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.cloud import storage
from PyPDF2 import PdfReader
import docx
from io import BytesIO
import os
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def initialize_vertex_ai(project_id, location):
    """Initializes the Vertex AI environment."""
    try:
        vertexai.init(project=project_id, location=location)
        logger.info("Vertex AI initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI: {e}")
        raise

def download_file_from_gcs(file_uri):
    """Downloads a file from Google Cloud Storage."""
    try:
        storage_client = storage.Client()
        bucket_name, blob_name = file_uri.replace("gs://", "").split("/", 1)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        file_content = blob.download_as_bytes()
        logger.info(f"File downloaded successfully from GCS: {file_uri}")
        return file_content
    except Exception as e:
        logger.error(f"Error downloading from GCS: {e}")
        return None

def upload_local_file_to_gcs(file_path, bucket_name, destination_blob_name):
    """Uploads a local file to Google Cloud Storage."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(file_path)
        logger.info(f"File uploaded successfully to GCS: {destination_blob_name}")
        return f"gs://{bucket_name}/{destination_blob_name}"
    except Exception as e:
        logger.error(f"Error uploading to GCS: {e}")
        return None

def extract_text_from_pdf(file_content):
    """Extracts text from a PDF file."""
    try:
        with BytesIO(file_content) as file:
            reader = PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
        logger.info("Text extracted successfully from PDF.")
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return ""

def extract_text_from_docx(file_content):
    """Extracts text from a DOCX file."""
    try:
        with BytesIO(file_content) as file:
            doc = docx.Document(file)
            text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
        logger.info("Text extracted successfully from DOCX.")
        return text
    except Exception as e:
        logger.error(f"Error extracting text from DOCX: {e}")
        return ""

def extract_text_from_txt(file_content):
    """Extracts text from a TXT file."""
    try:
        text = file_content.decode('utf-8')
        logger.info("Text extracted successfully from TXT.")
        return text
    except Exception as e:
        logger.error(f"Error extracting text from TXT: {e}")
        return ""

def call_vertex_ai(file_uri):
    """Calls Vertex AI to analyze the extracted text and returns the analysis in JSON format."""
    file_content = download_file_from_gcs(file_uri)
    
    if not file_content:
        logger.error(f"Failed to download file from GCS: {file_uri}")
        return {"error": "Failed to download file from GCS."}
    
    file_extension = os.path.splitext(file_uri)[1].lower()
    
    if file_extension == '.pdf':
        file_text = extract_text_from_pdf(file_content)
    elif file_extension == '.docx':
        file_text = extract_text_from_docx(file_content)
    elif file_extension == '.txt':
        file_text = extract_text_from_txt(file_content)
    else:
        logger.warning(f"Unsupported file type: {file_extension}")
        return {"error": "Unsupported file type."}
    
    if not file_text.strip():
        logger.warning("No text extracted from the file.")
        return {"error": "No text extracted from the file."}
    
    try:
        logger.info("Initializing Vertex AI with the given project ID and location.")
        project_id = "genaiq"
        location = "us-central1"
        initialize_vertex_ai(project_id, location)

        logger.info("Loading the Vertex AI generative model.")
        model = GenerativeModel("gemini-1.5-flash-001",
                                generation_config={"response_mime_type": "application/json"})

        logger.info("Preparing the prompt for Vertex AI.")
        prompt = (
            "You are an HR expert with extensive experience in evaluating resumes. "
            "Please review the following resume and provide detailed feedback on the candidate's qualifications, achievements, "
            "and potential for career growth. Highlight areas of strength and suggest improvements. Also, provide an ATS match percentage "
            "for the resume. Structure the feedback with the following fields:\n\n Esure the summary is the first field returned"
            "1. 'overall_feedback': A summary of the overall quality of the resume, including first impressions and overall strengths. \n"
            "2. 'feedback_cards': A list of sections, each containing:\n"
            "   - 'title': The section title (e.g., Professional Experience, Skills and Technologies, Contact Information, etc.).\n"
            "   - 'description': Detailed feedback on the section, focusing on clarity, relevance, and effectiveness.\n"
            "   - 'ats_match': An ATS match percentage for this section based on common applicant tracking system criteria.\n"
            "   - 'recommendations': Specific, actionable suggestions for improvement, aimed at enhancing clarity, impact, and ATS compatibility.\n"
            "Return the response in JSON format. Ensure the tone is clear and professional, yet friendly and engaging. "
            "Personalize the feedback by using the candidate's name throughout the review, making the advice feel tailored and considerate."
        )


        logger.info("Creating a Part object from the extracted file text.")
        part = Part.from_text(file_text)

        logger.info("Sending the prompt to Vertex AI for content generation.")
        response = model.generate_content([part, prompt])
        
        if response and response.text:
            logger.info("Received response from Vertex AI.")
            response_text = response.text
            
            logger.debug(f"Raw response text: {response_text}")

            try:
                return json.loads(response_text.strip('```json').strip('```').strip())
            except json.JSONDecodeError as json_err:
                logger.error(f"Failed to parse JSON response: {json_err}")
                return {"error": "Failed to parse JSON response.", "raw_response": response_text}
        else:
            logger.warning("No response received from Vertex AI.")
            return {"error": "No response received from Vertex AI."}

    except Exception as e:
        logger.error(f"Error in call_vertex_ai: {e}")
        return {"error": f"Error processing the file: {str(e)}"}


def roast_resume(file_uri):
    """Calls Vertex AI to analyze the extracted text and returns the analysis in JSON format."""
    try:
        file_content = download_file_from_gcs(file_uri)
        
        if not file_content:
            logger.error(f"Failed to download file from GCS: {file_uri}")
            return {"error": "Failed to download file from GCS."}
        
        file_extension = os.path.splitext(file_uri)[1].lower()
        
        if file_extension == '.pdf':
            file_text = extract_text_from_pdf(file_content)
        elif file_extension == '.docx':
            file_text = extract_text_from_docx(file_content)
        elif file_extension == '.txt':
            file_text = extract_text_from_txt(file_content)
        else:
            logger.warning(f"Unsupported file type: {file_extension}")
            return {"error": "Unsupported file type."}
        
        if not file_text.strip():
            logger.warning("No text extracted from the file.")
            return {"error": "No text extracted from the file."}
        
        logger.info("Initializing Vertex AI with the given project ID and location.")
        project_id = "genaiq"
        location = "us-central1"
        initialize_vertex_ai(project_id, location)

        logger.info("Loading the Vertex AI generative model.")
        model = GenerativeModel("gemini-1.5-flash-001", generation_config={"response_mime_type": "application/json"})

        logger.info("Preparing the prompt for Vertex AI.")
        prompt = (
        "Imagine you are a comedian like Kevin Hart, known for your sharp wit and humor. You are given a resume to review and roast. Your goal is to make the review funny and engaging"
        "Craft a single, cohesive roast that includes:\n\n"
        "1. Make fun of job titles, company names, and the way responsibilities are described. Point out any exaggerations or clichés.\n"
        "2. Make jokes about the keywords used in the resume that seem trendy or overused.\n"
        "3. A funny conclusion with a tiny bit of actual advice\n\n"
        "Keep the entire roast concise (about 4-6 sentences total) and funny. "
        "Structure your response in JSON format with a single 'roast' field. "
        "Strip all special characters for easy JSON parsing. "
        "Example structure:\n"
        "{\n"
        "  'roast': 'Yo, this resume... [full roast content here]'\n"
        "}"
)

        logger.info("Creating a Part object from the extracted file text.")
        part = Part.from_text(file_text)

        logger.info("Sending the prompt to Vertex AI for content generation.")
        response = model.generate_content([part, prompt])
        
        if response and response.text:
            logger.info("Received response from Vertex AI.")
            response_text = response.text
            
            logger.debug(f"Raw response text: {response_text}")

            try:
                # Strip JSON formatting characters and parse
                # clean_response = response_text.strip().strip('```json').strip('```').strip()
                return json.loads(response_text)
            except json.JSONDecodeError as json_err:
                logger.error(f"Failed to parse JSON response: {json_err}")
                return {"error": "Failed to parse JSON response.", "raw_response": response_text}
        else:
            logger.warning("No response received from Vertex AI.")
            return {"error": "No response received from Vertex AI."}

    except Exception as e:
        logger.error(f"Error in roast_resume: {e}")
        return {"error": f"Error processing the file: {str(e)}"}