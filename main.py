from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from requests.exceptions import RequestException
import os
from dotenv import load_dotenv
from typing import Optional, Dict
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI(title="RLM API Server", description="FastAPI server for RLM capacity management")

# Pydantic models for request/response
class ScheduleRequest(BaseModel):
    clientCode: str
    clientOrderNumber: str
    scheduledDate: str
    consigneeName: str
    phoneNumber: str
    aiConsent: str
    consentDateTime: str
    questions: str  # JSON string of question numbers to Y/N responses

class ScheduleResponse(BaseModel):
    success: bool
    status_code: int
    response_data: Optional[dict] = None
    error_message: Optional[str] = None

def handle_null_or_empty(value: str, default: str = "") -> str:
    """Handle null, empty, or string 'null' values"""
    if not value or value.strip() == "" or value.lower() in ["null", "none"]:
        return default
    return value

def transform_questions(questions_json_string: str) -> list:
    """Transform JSON string of questions to required API format"""
    # Handle null or empty questions
    if not questions_json_string or questions_json_string.strip() == "":
        return []  # Return empty list if no questions provided
    else:
        try:
            questions_dict = json.loads(questions_json_string)
        except json.JSONDecodeError:
            return []  # Return empty list if JSON parsing fails
    
    # If questions_dict is empty, return empty list
    if not questions_dict:
        return []
    
    transformed = []
    question_id = 1  # Start with ID 1 and increment
    for question_text, response in questions_dict.items():
        # Use "na" if response is empty or null
        final_response = response if response else "na"
        transformed.append({
            "questionDescription": question_text,
            "questionId": question_id,
            "questionResponse": final_response.lower()
        })
        question_id += 1  # Increment for next question
    return transformed

def transform_ai_consent(consent_value: str) -> str:
    """Transform string consent to "true" or "false" string"""
    cleaned_value = handle_null_or_empty(consent_value, "false")
    if cleaned_value.lower() in ['true', 'yes', '1', 'y']:
        return "true"
    else:
        return "false"

def transform_consent_datetime(datetime_string: str) -> str:
    """Transform datetime string to ISO format YYYY-MM-DDTHH:MM:SS"""
    from datetime import datetime
    import re
    
    # Handle null, empty, or "null" cases using the helper function
    cleaned_datetime = handle_null_or_empty(datetime_string, "")
    if cleaned_datetime == "":
        # Return current datetime in ISO format as default
        return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    
    # If it's already in correct ISO format, return as is
    iso_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$'
    if re.match(iso_pattern, cleaned_datetime):
        return cleaned_datetime
    
    # Try to parse common formats and convert to ISO
    try:
        # Handle format like "Monday, August 4, 2025 4:50:15 AM EDT"
        # Remove day name and timezone
        cleaned = re.sub(r'^[A-Za-z]+,\s*', '', cleaned_datetime)  # Remove "Monday, "
        cleaned = re.sub(r'\s+[A-Z]{3,4}$', '', cleaned)  # Remove " EDT"
        
        # Parse and format to ISO
        dt = datetime.strptime(cleaned, '%B %d, %Y %I:%M:%S %p')
        return dt.strftime('%Y-%m-%dT%H:%M:%S')
    except:
        # If parsing fails, try other common formats
        try:
            dt = datetime.fromisoformat(cleaned_datetime.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%dT%H:%M:%S')
        except:
            # Default fallback to current datetime
            return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

def transform_schedule_date(date_string: str) -> str:
    """Transform date string to YYYY-MM-DD format"""
    from datetime import datetime
    import re
    
    logger.info(f"Schedule date input: '{date_string}'")
    
    # Handle null, empty, or "null" cases
    cleaned_date = handle_null_or_empty(date_string, "")
    if cleaned_date == "":
        result = datetime.now().strftime('%Y-%m-%d')
        logger.info(f"Schedule date was empty, using current date: '{result}'")
        return result
    
    # If it's already in correct format, return as is
    date_pattern = r'^\d{4}-\d{2}-\d{2}$'
    if re.match(date_pattern, cleaned_date):
        logger.info(f"Schedule date already in correct format: '{cleaned_date}'")
        return cleaned_date
    
    # Try to parse common date formats
    try:
        # Try various date formats
        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%B %d, %Y', '%d %B %Y']:
            try:
                dt = datetime.strptime(cleaned_date, fmt)
                result = dt.strftime('%Y-%m-%d')
                logger.info(f"Schedule date transformed from '{cleaned_date}' to '{result}' using format '{fmt}'")
                return result
            except ValueError:
                continue
        
        # If no format worked, return current date
        result = datetime.now().strftime('%Y-%m-%d')
        logger.warning(f"Could not parse schedule date '{cleaned_date}', using current date: '{result}'")
        return result
    except:
        # Default fallback to current date
        result = datetime.now().strftime('%Y-%m-%d')
        logger.error(f"Error parsing schedule date '{cleaned_date}', using current date: '{result}'")
        return result

@app.get("/")
async def root():
    """Health check endpoint"""
    logger.info("Health check endpoint hit")
    return {"message": "RLM API Server is running"}

@app.post("/schedule-appointment", response_model=ScheduleResponse)
async def schedule_appointment(request: ScheduleRequest):
    """
    Make a POST request to the RLM API endpoint for AI Schedule Confirmation
    """
    logger.info(f"Schedule appointment request received")
    logger.info(f"Schedule Date: {request.scheduledDate}")
    logger.info(f"Client Order Number: {request.clientOrderNumber}")
    logger.info(f"Client Code: {request.clientCode}")
    
    # API endpoint
    url = "https://apiqa.ryder.com/rlm/ryderview/capacitymanagement/api/ScheduleAppointment/AIScheduleConfirmation"
    
    # Get header from environment variable
    api_header_value = os.getenv("API_HEADER_VALUE")
    if not api_header_value:
        logger.error("API_HEADER_VALUE not found in environment variables")
        raise HTTPException(
            status_code=500, 
            detail="API_HEADER_VALUE not found in environment variables. Please check your .env file."
        )
    
    # Prepare headers (using subscription key instead of Authorization)
    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": api_header_value,  # Common subscription key header name
    }
    
    # Transform questions from dict to required format
    transformed_questions = transform_questions(request.questions)
    logger.info(f"Transformed {len(transformed_questions)} questions")
    
    # Prepare request body using values from incoming payload
    payload = {
        "clientCode": handle_null_or_empty(request.clientCode, ""),
        "clientOrderNumber": handle_null_or_empty(request.clientOrderNumber, ""),
        "scheduledDate": transform_schedule_date(request.scheduledDate),
        "consigneeName": handle_null_or_empty(request.consigneeName, ""),
        "phoneNumber": handle_null_or_empty(request.phoneNumber, ""),
        "aiConsent": transform_ai_consent(request.aiConsent),
        "consentDateTime": transform_consent_datetime(request.consentDateTime),
        "questions": transformed_questions
    }
    
    logger.info(f"Final payload scheduled date: {payload['scheduledDate']}")
    logger.info(f"Making request to RLM API")
    
    try:
        # Make the POST request
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        logger.info(f"RLM API response status: {response.status_code}")
        
        # Parse response
        response_data = None
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            response_data = {"raw_response": response.text}
        
        # Determine if request was successful
        is_successful = response.status_code == 200
        
        if is_successful:
            logger.info("✅ REQUEST SUCCESSFUL - RLM API returned 200")
            logger.info(f"Success response data: {response_data}")
        else:
            logger.error(f"❌ REQUEST FAILED - RLM API returned {response.status_code}")
            logger.error(f"Error response data: {response_data}")
            logger.error(f"Error response text: {response.text}")
        
        result = ScheduleResponse(
            success=is_successful,
            status_code=response.status_code,
            response_data=response_data,
            error_message=None if is_successful else f"HTTP {response.status_code}: {response.text}"
        )
        
        logger.info(f"Final result - Success: {result.success}, Status: {result.status_code}")
        return result
        
    except RequestException as e:
        logger.error(f"🚨 NETWORK ERROR - Failed to reach RLM API: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error making request to RLM API: {str(e)}"
        )

@app.post("/schedule-appointment-custom")
async def schedule_appointment_custom(payload: dict):
    """
    Make a POST request with custom payload to the RLM API endpoint
    """
    # API endpoint
    url = "https://apiqa.ryder.com/rlm/ryderview/capacitymanagement/api/ScheduleAppointment/AIScheduleConfirmation"
    
    # Get header from environment variable
    api_header_value = os.getenv("API_HEADER_KEY")
    if not api_header_value:
        raise HTTPException(
            status_code=500, 
            detail="API_HEADER_KEY not found in environment variables. Please check your .env file."
        )
    
    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": api_header_value,  # Common subscription key header name
    }
    
    try:
        # Make the POST request
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        # Parse response
        response_data = None
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            response_data = {"raw_response": response.text}
        
        return ScheduleResponse(
            success=response.status_code == 200,
            status_code=response.status_code,
            response_data=response_data,
            error_message=None if response.status_code == 200 else f"HTTP {response.status_code}: {response.text}"
        )
        
    except RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error making request to RLM API: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 