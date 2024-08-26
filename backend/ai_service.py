import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.cloud import storage
from PyPDF2 import PdfReader

def initialize_vertex_ai(project_id, location):
    vertexai.init(project=project_id, location=location)

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

def extract_text_from_pdf(file_path):
    try:
        with open(file_path, "rb") as file:
            reader = PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
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
        )

        part = Part.from_text(file_text)

        response = model.generate_content([part, prompt])
        return response.text
    except Exception as e:
        print(f"Error calling Vertex AI: {e}")
        return "Error processing the file."

def process_file(file_path):
    bucket_name = 'genaiq_cloudbuild'
    destination_blob_name = 'uploads/test_document.pdf'

    file_uri = upload_local_file_to_gcs(file_path, bucket_name, destination_blob_name)
    
    if file_uri:
        file_text = extract_text_from_pdf(file_path)
        
        if file_text.strip():
            result = call_vertex_ai(file_text)
            return result
        else:
            return "No text extracted from the PDF."
    else:
        return "Failed to upload file to GCS."

if __name__ == "__main__":
    local_file_path = '/home/bishoptewogbade/genaiq/backend/static/uploads/resume.pdf'
    print(process_file(local_file_path))
