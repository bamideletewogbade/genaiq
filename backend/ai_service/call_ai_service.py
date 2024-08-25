import vertexai
from vertexai.generative_models import GenerativeModel, Part

# Replace 'your-project-id' with your actual Google Cloud project ID
PROJECT_ID = 'genaiq'

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location="us-central1")

# Initialize the model
model = GenerativeModel("gemini-1.5-flash-001")

# Define the GCS URI of the file to analyze and the prompt
gcs_uri = "gs://cloud-samples-data/generative-ai/image/scones.jpg"
mime_type = "image/jpeg"
prompt = "What is shown in this image?"

# Create a Part object from the GCS URI
part = Part.from_uri(gcs_uri, mime_type=mime_type)

# Generate content
response = model.generate_content([part, prompt])

# Print the response
print(response.text)
