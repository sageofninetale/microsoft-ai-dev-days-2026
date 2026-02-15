# Backend API

FastAPI service for processing patient handoff data using Azure OpenAI and Azure Speech Services.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure `.env` file exists in the project root with:
```
AZURE_OPENAI_ENDPOINT=<your-endpoint>
AZURE_OPENAI_KEY=<your-key>
AZURE_OPENAI_DEPLOYMENT=<your-deployment-name>
AZURE_SPEECH_KEY=<your-speech-key>
AZURE_SPEECH_REGION=<your-region>
```

## Running the Server

```bash
cd backend
python main.py
```

The API will start on `http://localhost:8000`

## API Endpoints

### `GET /`
Health check endpoint.

### `POST /handoff/intake`
Process a patient handoff transcript and extract structured data.

**Request Body:**
```json
{
  "transcript": "Patient John Doe in room 302..."
}
```

**Response:**
```json
{
  "patient_name": "John Doe",
  "room_number": "302",
  "age": "68",
  "chief_complaint": "chest pain",
  "medications": ["aspirin 81mg daily", "metoprolol 50mg twice daily"],
  "pending_tasks": ["cardiac enzyme labs at 6 AM"],
  "vitals": {"blood_pressure": "145/92", "heart_rate": "88"},
  "safety_alerts": ["fall risk due to dizziness"]
}
```

## Testing

Run the test script:
```bash
python test_intake_api.py
```

## Architecture

- `main.py` - FastAPI application with CORS middleware
- `intake_agent.py` - Azure OpenAI integration for data extraction
- `test_intake_api.py` - Sample client for testing the API
