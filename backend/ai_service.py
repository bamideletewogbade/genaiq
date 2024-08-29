import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.cloud import storage
from PyPDF2 import PdfReader
from PyPDF2 import PdfWriter
from pypdf import PdfReader
from pypdf import PdfWriter
import docx
from io import BytesIO

pdf_writer = PdfWriter()
page = pdf_writer.add_blank_page(width=8.27 * 72, height=11.7 * 72)

def initialize_vertex_ai(project_id, location):
    vertexai.init(project=project_id, location=location)

def download_file_from_gcs(file_uri):
    try:
        storage_client = storage.Client()
        bucket_name, blob_name = file_uri.replace("gs://", "").split("/", 1)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        file_content = blob.download_as_bytes()
        return file_content
    except Exception as e:
        print(f"Error downloading from GCS: {e}")
        return None

def upload_local_file_to_gcs(file_path, bucket_name, destination_blob_name):
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(file_path)
        return f"gs://{bucket_name}/{destination_blob_name}"
            
    except Exception as e:
            print(f"Error uploading to GCS: {e}")
            return None

def process_file(file_uri):
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
            return "Unsupported file type."

        if file_text.strip():
            result = call_vertex_ai(file_text)
            return result
        else:
            return "No text extracted from the file."
    else:
        return "Failed to download file from GCS."


def extract_text_from_pdf(file_content):
    try:
        with BytesIO(file_content) as file:
            reader = PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""

def extract_text_from_docx(file_content):
    try:
        with BytesIO(file_content) as file:
            doc = docx.Document(file)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
        return text
    except Exception as e:
        print(f"Error extracting text from DOCX: {e}")
        return ""

def extract_text_from_txt(file_content):
    try:
        text = file_content.decode('utf-8')
        return text
    except Exception as e:
        print(f"Error extracting text from TXT: {e}")
        return ""

def call_vertex_ai(file_text):
    try:
        project_id = "genaiq"
        location = "us-central1"
        initialize_vertex_ai(project_id, location)

        model = GenerativeModel("gemini-1.5-flash-001")

        prompt = (
            "As an HR expert with extensive experience, please review the following CV and provide detailed feedback "
            "on how well it showcases the candidate's qualifications, achievements, and overall potential for career growth. "
            "Highlight areas of strength and suggest improvements where applicable."

           " <h3>Overall Feedback</h3>"
            "<p>{{ analysis_result.overall }}</p>"
           " <h3>Content</h3>"
           " <p>{{ analysis_result.content }}</p>"
           " <h3>Structure</h3>"
           " <p>{{ analysis_result.structure }}</p> "
           " <h3>Formatting</h3>"
          "  <p>{{ analysis_result.formatting }}</p>"
         "   <h3>Language</h3>"
           " <p>{{ analysis_result.language }}</p>"

        )

        part = Part.from_text(file_text)

        response = model.generate_content([part, prompt])
        print(response)
        return response.text
    except Exception as e:
        print(f"Error calling Vertex AI: {e}")
        return "Error processing the file."

