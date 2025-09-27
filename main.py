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
    groupId: Optional[str] = None
    real_questions: Optional[str] = None

class AvailableDatesRequest(BaseModel):
    clientCode: str
    clientOrderNumber: str

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
    """Transform JSON string of questions to required API format - handles variable number of questions"""
    # Handle null or empty questions
    if not questions_json_string or questions_json_string.strip() == "":
        logger.info("No questions provided, returning empty list")
        return []
    
    try:
        questions_dict = json.loads(questions_json_string)
    except json.JSONDecodeError:
        logger.warning("Failed to parse questions JSON, returning empty list")
        return []
    
    if not questions_dict:
        logger.info("Questions dict is empty, returning empty list")
        return []
    
    # Create questions with sequential IDs
    transformed = []
    question_id = 1
    
    for question_text, response in questions_dict.items():
        # Use "na" if response is empty or null
        final_response = response if response else "na"
        
        transformed.append({
            "questionDescription": question_text,
            "questionId": question_id,
            "questionResponse": final_response.lower()
        })
        
        question_id += 1
    
    logger.info(f"Created {len(transformed)} questions for API with IDs 1-{len(transformed)}")
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
    
    # Check if it's a datetime string and extract just the date part
    datetime_patterns = [
        r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?$',  # ISO datetime with optional Z
        r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z?$',  # ISO datetime with milliseconds
        r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$'  # Space-separated datetime
    ]
    
    for pattern in datetime_patterns:
        if re.match(pattern, cleaned_date):
            try:
                # Extract just the date part (first 10 characters for YYYY-MM-DD)
                date_part = cleaned_date[:10]
                logger.info(f"Extracted date part from datetime '{cleaned_date}' to '{date_part}'")
                return date_part
            except:
                continue
    
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

def fetch_available_dates_and_questions(client_code: str, client_order_number: str) -> Optional[dict]:
    """Fetch available dates and questions from the API"""
    url = "https://api.ryder.com/rlm/ryderview/capacitymanagement/api/ScheduleAppointment/AvailableDates"
    
    # Get header from environment variable
    api_header_value = os.getenv("API_HEADER_VALUE")
    if not api_header_value:
        logger.error("API_HEADER_VALUE not found for available dates request")
        return None
    
    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": api_header_value,
    }
    
    payload = {
        "clientCode": client_code,
        "clientOrderNumber": client_order_number
    }
    
    try:
        logger.info(f"Fetching available dates and questions for order: {client_order_number}")
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Successfully fetched {len(data.get('questions', []))} questions from API")
            return data
        else:
            logger.error(f"Failed to fetch available dates: {response.status_code} - {response.text}")
            return None
            
    except RequestException as e:
        logger.error(f"Error fetching available dates: {str(e)}")
        return None

@app.get("/")
async def root():
    """Health check endpoint"""
    logger.info("Health check endpoint hit")
    return {"message": "RLM API Server is running"}

@app.get("/test")
async def test():
    """Simple test endpoint"""
    logger.info("Test endpoint hit")
    return {"status": "ok", "message": "Railway deployment is working"}

@app.post("/available-dates")
async def get_available_dates(request: AvailableDatesRequest):
    """Get available dates and questions from RLM API"""
    logger.info(f"Available dates request for order: {request.clientOrderNumber}")
    
    data = fetch_available_dates_and_questions(request.clientCode, request.clientOrderNumber)
    
    if data:
        return {
            "success": True,
            "availableDates": data.get("availableDates", []),
            "questions": data.get("questions", [])
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch available dates and questions"
        )

def transform_questions_with_api_match(questions_json_string: str, api_questions: list) -> list:
    """Transform questions matching against API questions by order"""
    # Handle null or empty questions
    if not questions_json_string or questions_json_string.strip() == "":
        logger.info("No questions provided, using API questions with empty responses")
        # Return API questions with empty responses
        return [{
            "questionDescription": q["questionDescription"],
            "questionId": q["questionId"],
            "questionResponse": ""
        } for q in api_questions]
    
    try:
        user_questions_dict = json.loads(questions_json_string)
    except json.JSONDecodeError:
        logger.warning("Failed to parse questions JSON, using API questions with empty responses")
        return [{
            "questionDescription": q["questionDescription"],
            "questionId": q["questionId"],
            "questionResponse": ""
        } for q in api_questions]
    
    if not user_questions_dict:
        logger.info("Questions dict is empty, using API questions with empty responses")
        return [{
            "questionDescription": q["questionDescription"],
            "questionId": q["questionId"],
            "questionResponse": ""
        } for q in api_questions]
    
    # Convert user questions to a list to match by order
    user_questions_list = list(user_questions_dict.items())
    transformed = []
    
    for i, api_question in enumerate(api_questions):
        if i < len(user_questions_list):
            # Use user's response for this position
            user_question_text, user_response = user_questions_list[i]
            final_response = user_response if user_response else "na"
            logger.info(f"Question {i+1}: Using user response '{final_response}' for API question")
        else:
            # No user response for this position
            final_response = "na"
            logger.info(f"Question {i+1}: No user response, using 'na'")
        
        transformed.append({
            "questionDescription": api_question["questionDescription"],
            "questionId": api_question["questionId"],
            "questionResponse": final_response.lower()
        })
    
    logger.info(f"Matched {len(transformed)} questions with API questions")
    return transformed

@app.post("/schedule-appointment", response_model=ScheduleResponse)
async def schedule_appointment(request: ScheduleRequest):
    """
    Make a POST request to the RLM API endpoint for AI Schedule Confirmation
    """
    logger.info(f"Schedule appointment request received")
    logger.info(f"Schedule Date: {request.scheduledDate}")
    logger.info(f"Client Order Number: {request.clientOrderNumber}")
    logger.info(f"Client Code: {request.clientCode}")

    ##### took this out because we are not using the API questions right now
    
    # # First, fetch the available dates and questions to get the correct question format
    # api_data = fetch_available_dates_and_questions(request.clientCode, request.clientOrderNumber)
    # if not api_data or "questions" not in api_data:
    #     logger.error("Failed to fetch API questions, cannot proceed with scheduling")
    #     raise HTTPException(
    #         status_code=500,
    #         detail="Failed to fetch required questions from API"
    #     )
    
    # api_questions = api_data["questions"]
    # logger.info(f"Fetched {len(api_questions)} questions from API")

    ######
    if request.real_questions:
        api_questions = json.loads(request.real_questions)
    else:
        api_questions = []
    
    # API endpoint
    url = "https://api.ryder.com/rlm/ryderview/capacitymanagement/api/ScheduleAppointment/AIUpdateQuestionnaireResponse"
    
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
    
    # Transform questions using API questions as the template
    transformed_questions = transform_questions_with_api_match(request.questions, api_questions)


    logger.info(f"Transformed {len(transformed_questions)} questions using API template")
    
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
    # Include groupId if provided
    clean_group = handle_null_or_empty(request.groupId, "") if request.groupId is not None else ""
    if clean_group != "":
        payload["groupId"] = clean_group
    
    logger.info(f"Final payload scheduled date (date only, no time): {payload['scheduledDate']}")
    logger.info(f"Final payload consent datetime (with time): {payload['consentDateTime']}")
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
    url = "https://api.ryder.com/rlm/ryderview/capacitymanagement/api/ScheduleAppointment/AIScheduleConfirmation"
    
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