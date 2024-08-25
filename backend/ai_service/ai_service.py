import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.cloud import storage
from PyPDF2 import PdfReader

def initialize_vertex_ai(project_id, location):
    """Initializes Vertex AI with the given project and location."""
    vertexai.init(project=project_id, location=location)

def upload_local_file_to_gcs(file_path, bucket_name, destination_blob_name):
    """Uploads a local file to Google Cloud Storage."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(file_path)
        print(f"File {file_path} uploaded to {destination_blob_name}.")
        return f"gs://{bucket_name}/{destination_blob_name}"
    except Exception as e:
        print(f"Error uploading to GCS: {e}")
        return None

def extract_text_from_pdf(file_path):
    """Extracts text from a PDF file."""
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
    """Calls Vertex AI with text and a feedback prompt."""
    try:
        # Initialize Vertex AI
        project_id = "genaiq"
        location = "us-central1"
        initialize_vertex_ai(project_id, location)

        # Load the model
        model = GenerativeModel("gemini-1.5-flash-001")

        # Define the feedback prompt
        prompt = (
            "As an HR expert with extensive experience, please review the following CV and provide detailed feedback "
            "on how well it showcases the candidate's qualifications, achievements, and overall potential for career growth. "
            "Highlight areas of strength and suggest improvements where applicable."
        )

        # Create a Part object from the text
        part = Part.from_text(file_text)

        # Generate content
        response = model.generate_content([part, prompt])
        return response.text
    except Exception as e:
        print(f"Error calling Vertex AI: {e}")
        return "Error processing the file."

def test_local_pdf(file_path, bucket_name, destination_blob_name):
    """Tests Vertex AI with a local PDF file."""
    # Upload the local file to GCS
    file_uri = upload_local_file_to_gcs(file_path, bucket_name, destination_blob_name)
    
    if file_uri:
        # Extract text from the PDF
        file_text = extract_text_from_pdf(file_path)
        
        if file_text.strip():  # Ensure the text is not empty
            # Call Vertex AI with the extracted text
            result = call_vertex_ai(file_text)
            print(result)
        else:
            print("No text extracted from the PDF.")
    else:
        print("Failed to upload file to GCS.")

# Example usage
if __name__ == "__main__":
    # Define parameters
    local_file_path = '/home/bishoptewogbade/genaiq/backend/upload_service/uploads/resume.pdf'  # Replace with your local PDF path
    gcs_bucket_name = 'genaiq_cloudbuild'  # Replace with your GCS bucket name
    gcs_blob_name = 'uploads/test_document.pdf'  # The desired path in GCS

    # Run the test
    test_local_pdf(local_file_path, gcs_bucket_name, gcs_blob_name)
