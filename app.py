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
async def upload_file(audio: UploadFile = File(...), transcript: str = Form(...)):
    try:
        # Convert uploaded audio to WAV format if it's not already in WAV
        if audio.filename.endswith('.wav'):
            wav_filename = audio.filename
        else:
            wav_filename = convert_to_wav(audio.file, audio.filename)

        blob_name = f"{uuid.uuid4()}.wav"
        blob_client = container_client.get_blob_client(blob_name)

        with open(wav_filename, "rb") as audio_file:
            audio_data = audio_file.read()
            blob_client.upload_blob(audio_data, blob_type="BlockBlob")

        audio_url = blob_client.url

        document = {
            "audioUrl": audio_url,
            "transcript": transcript
        }

        await collection.insert_one(document)

        return JSONResponse(status_code=200, content={"audioUrl": audio_url, "transcript": transcript})
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
