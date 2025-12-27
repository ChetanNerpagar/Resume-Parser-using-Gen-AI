# import libraries
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import yaml
import json
import re
import time

api_key = None
CONFIG_PATH = r"config.yaml"

try:
    with open(CONFIG_PATH, 'r') as file:
        config = yaml.safe_load(file)
        api_key = config['GEMINI_API_KEY']
except Exception as e:
    print(f"Error loading config: {e}")
    raise

def clean_json_response(text):
    # Remove markdown code block markers if present
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()

def ats_extractor(resume_data, max_retries=1, initial_delay=1):
    """
    Extract ATS data from resume using Gemini API with retry logic for rate limits.
    
    Args:
        resume_data: The resume text content
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before retrying
    
    Returns:
        JSON string with extracted data or error message
    """
    prompt = '''
    You are an AI bot designed to act as a professional for parsing resumes. You are given with resume and your job is to extract the following information from the resume:
    1. full name
    2. email id
    3. github portfolio
    4. linkedin id
    5. employment details
    6. technical skills
    7. soft skills
    8. contact number
    9. address
    10. Projects
    IMPORTANT: Your response must be a valid JSON object with the following structure:
    {
        "full_name": "extracted name",
        "email_id": "extracted email",
        "github_portfolio": "extracted github url",
        "linkedin_id": "extracted linkedin url",
        "employment_details": ["list of employment details"],
        "technical_skills": ["list of technical skills"],
        "soft_skills": ["list of soft skills"],
        "contact_number": ["extracted contact number"],
        "address": ["extracted address"],
        "Projects": ["list of projects"]
    }
    
    Only return the JSON object, no additional text or explanation.
    '''

    # Configure the Gemini API
    genai.configure(api_key=api_key)
    
    # Initialize the model
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # Combine the prompt and resume data
    full_prompt = f"{prompt}\n\nResume Content:\n{resume_data}"
    
    # Retry logic for rate limit errors
    for attempt in range(max_retries + 1):
        try:
            # Generate response
            response = model.generate_content(full_prompt)
            
            # Extract the text from the response and ensure it's valid JSON
            try:
                data = response.text.strip()
                # Clean the response from markdown formatting
                cleaned_data = clean_json_response(data)
                # Try to parse the response as JSON to validate it
                json.loads(cleaned_data)
                return cleaned_data
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON response: {e}")
                print(f"Raw response: {data}")
                # Return a basic JSON structure if parsing fails
                return json.dumps({
                    "error": "Failed to parse resume data",
                    "raw_response": data
                })
        
        except google_exceptions.ResourceExhausted as e:
            # Extract retry delay from error if available
            error_str = str(e)
            retry_delay = None
            
            # Try to extract retry delay from error message
            if "retry_delay" in error_str or "Please retry in" in error_str:
                delay_match = re.search(r'retry in ([\d.]+)s', error_str, re.IGNORECASE)
                if delay_match:
                    retry_delay = float(delay_match.group(1))
            
            # If rate limit exceeded, fail fast instead of waiting long periods
            # Only retry if the delay is reasonable (less than 10 seconds)
            if retry_delay and retry_delay < 10 and attempt < max_retries:
                wait_time = retry_delay + 1  # Add 1 second buffer, no exponential backoff
                print(f"Rate limit exceeded. Retrying in {wait_time:.2f} seconds... (Attempt {attempt + 1}/{max_retries + 1})")
                time.sleep(wait_time)
            else:
                # Rate limit delay is too long or max retries exceeded - fail fast
                error_message = (
                    "API rate limit exceeded. You have reached the free tier quota limit (20 requests per minute). "
                    "Please wait a few minutes before trying again, or upgrade your API plan."
                )
                print(error_message)
                return json.dumps({
                    "error": "Rate limit exceeded",
                    "message": error_message,
                    "suggestion": "Please wait a few minutes and try again, or check your API quota at https://ai.dev/usage?tab=rate-limit"
                })
        
        except Exception as e:
            # Handle other exceptions
            error_message = f"An error occurred while processing the resume: {str(e)}"
            print(error_message)
            return json.dumps({
                "error": "Processing error",
                "message": error_message
            })
    
    # Should not reach here, but just in case
    return json.dumps({
        "error": "Unknown error",
        "message": "Failed to process resume after multiple attempts"
    })