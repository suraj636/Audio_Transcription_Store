from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from azure.storage.blob import BlobServiceClient
from pymongo import MongoClient
import uuid
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
import soundfile as sf  # Import soundfile for audio operations
from fastapi.middleware.cors import CORSMiddleware  # Import CORS middleware

load_dotenv()

app = FastAPI()

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
MONGODB_URI = os.getenv("MONGODB_URI")
BLOB_CONTAINER_NAME = 'audiodata'

blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)

client = AsyncIOMotorClient(MONGODB_URI)
db = client["SpeechToText"]
collection = db["Audio_Transcription"]

# CORS configuration
origins = [
    "*"
]

# Function to convert audio to WAV format using soundfile
def convert_to_wav(audio_data, filename):
    wav_filename = f"{filename.split('.')[0]}.wav"
    with sf.SoundFile(audio_data) as audio_file:
        # Read audio data and write to WAV format
        audio_data, sample_rate = audio_file.read(dtype='float32')
        sf.write(wav_filename, audio_data, sample_rate, format='WAV')
    return wav_filename

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Speech-to-Text API"}

@app.post("/upload")
async def upload_audio(audio_file: UploadFile = File(...), sentence: str = Form(...)):
    try:
        # Generate a unique file name
        unique_id = str(uuid.uuid4())
        original_filename = audio_file.filename
        unique_filename = f"{unique_id}_{original_filename}"

        # Create a BlobServiceClient object
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

        # Create a BlobClient object
        blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=unique_filename)

        # Upload the audio file to Azure storage
        blob_client.upload_blob(audio_file.file, overwrite=True)

        # Get the URL of the uploaded blob
        blob_url = blob_client.url

        # Insert the audio URL and sentence into the database
        record = {"audio": blob_url, "transcription": sentence}
        collection.insert_one(record)

        return JSONResponse(content={"message": "Audio uploaded successfully!", "url": blob_url}, status_code=200)

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
