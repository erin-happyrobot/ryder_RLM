from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from requests.exceptions import RequestException
import os
from dotenv import load_dotenv
from typing import Optional, Dict
import json

# Load environment variables
load_dotenv()

app = FastAPI(title="RLM API Server", description="FastAPI server for RLM capacity management")

# Static question mapping
QUESTION_MAPPING = {
    "1": {
        "questionDescription": "Is this delivery being made within a gated community, a military installation, or any location with controlled or limited access?",
        "questionId": 1
    },
    "2": {
        "questionDescription": "If your order is set for Deluxe, White Glove, or Room of Choice service level, will the delivery team be going up or down MORE THAN 2 flights of stairs?  If you have any other service level please respond No as stairs will not apply.",
        "questionId": 2
    },
    "3": {
        "questionDescription": "Do you reside in a building or complex that requires a Certificate of Insurance for deliveries?",
        "questionId": 3
    },
    "4": {
        "questionDescription": "Are there any obstacles or tight turns that would require more than a 2-man team to complete your delivery?.",
        "questionId": 4
    },
    "5": {
        "questionDescription": "Does your order require an exchange of merchandise where we would be both delivering and picking up product from your home?",
        "questionId": 5
    }
}

# Pydantic models for request/response
class ScheduleRequest(BaseModel):
    clientCode: str
    clientOrderNumber: str
    scheduledDate: str
    consigneeName: str
    phoneNumber: str
    aiConsent: str
    consentDateTime: str
    questions: Dict[str, str]  # Dictionary of question keys to Y/N responses

class ScheduleResponse(BaseModel):
    success: bool
    status_code: int
    response_data: Optional[dict] = None
    error_message: Optional[str] = None

def transform_questions(questions_dict: Dict[str, str]) -> list:
    """Transform dictionary of questions to required API format"""
    transformed = []
    for key, response in questions_dict.items():
        if key in QUESTION_MAPPING:
            transformed.append({
                "questionDescription": QUESTION_MAPPING[key]["questionDescription"],
                "questionId": QUESTION_MAPPING[key]["questionId"],
                "questionResponse": response.lower()
            })
    return transformed

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "RLM API Server is running"}

@app.post("/schedule-appointment", response_model=ScheduleResponse)
async def schedule_appointment(request: ScheduleRequest):
    """
    Make a POST request to the RLM API endpoint for AI Schedule Confirmation
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
    
    # Prepare headers (using subscription key instead of Authorization)
    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": api_header_value,  # Common subscription key header name
    }
    
    # Transform questions from dict to required format
    transformed_questions = transform_questions(request.questions)
    
    # Prepare request body using values from incoming payload
    payload = {
        "clientCode": request.clientCode,
        "clientOrderNumber": request.clientOrderNumber,
        "scheduledDate": request.scheduledDate,
        "consigneeName": request.consigneeName,
        "phoneNumber": request.phoneNumber,
        "aiConsent": request.aiConsent,
        "consentDateTime": request.consentDateTime,
        "questions": transformed_questions
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