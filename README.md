# RLM FastAPI Server

A FastAPI server that makes POST requests to the RLM capacity management API endpoint.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create a `.env` file:**
   Copy `env.sample` to `.env` and add your API header value:
   ```bash
   cp env.sample .env
   ```
   Then edit `.env` and replace `your_header_value_here` with the actual header value.

3. **Run the server:**
   ```bash
   python main.py
   ```
   Or using uvicorn directly:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

## API Endpoints

### GET /
Health check endpoint that returns a simple status message.

### POST /schedule-appointment
Makes a POST request to the RLM API using the values from your request body. **A request body is required.**

**Required request body format:**
```json
{
  "clientCode": "RVCLNT1",
  "clientOrderNumber": "SALTESTRVT07302501",
  "scheduledDate": "2025-08-01",
  "consigneeName": "CSALTESTRVT07302501S1",
  "phoneNumber": "9259898099",
  "aiConsent": "true",
  "consentDateTime": "2025-07-30T00:00:00",
  "questions": "{}"
}
```

### POST /schedule-appointment-custom
Makes a POST request to the RLM API with a completely custom payload (accepts any JSON structure).

**Example usage:**
```bash
curl -X POST "http://localhost:8000/schedule-appointment" \
     -H "Content-Type: application/json" \
     -d '{
       "clientCode": "RVCLNT1",
       "clientOrderNumber": "SALTESTRVT07302501",
       "scheduledDate": "2025-08-01",
       "consigneeName": "CSALTESTRVT07302501S1",
       "phoneNumber": "9259898099",
       "aiConsent": "true",
       "consentDateTime": "2025-07-30T00:00:00",
       "questions": "{}"
     }'
```

Or with different data:
```bash
curl -X POST "http://localhost:8000/schedule-appointment" \
     -H "Content-Type: application/json" \
     -d '{
       "clientCode": "CUSTOM1",
       "clientOrderNumber": "CUSTOM123",
       "scheduledDate": "2025-09-01",
       "consigneeName": "Custom Name",
       "phoneNumber": "1234567890",
       "aiConsent": "true",
       "consentDateTime": "2025-08-01T00:00:00",
       "questions": "{}"
     }'
```

## Environment Variables

- `API_HEADER_VALUE`: The header value required for authentication with the RLM API

## Notes

- The server runs on `http://localhost:8000` by default
- Interactive API documentation is available at `http://localhost:8000/docs`
- The server expects the header to be an Authorization header, but you can modify the header name in the code if needed
- All fields in the request body are required for the `/schedule-appointment` endpoint 