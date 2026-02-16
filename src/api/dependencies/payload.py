from fastapi import Request, HTTPException
import yaml
import json
from src.core.logger import logger

async def get_payload(request: Request):
    """
    Dependency to parse the request body. 
    It prefers JSON but falls back to YAML if JSON parsing fails,
    making it "forgiving" for users who paste raw YAML into JSON fields.
    """
    content_type = request.headers.get("Content-Type", "").lower()
    body = await request.body()
    
    if not body:
        return {}

    # 1. Explicit YAML/YML header
    if "yaml" in content_type or "yml" in content_type:
        try:
            return yaml.safe_load(body)
        except yaml.YAMLError as e:
            logger.error(f"YAML Parse Error: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid YAML content: {e}")

    # 2. General case: Try JSON first, fallback to YAML
    try:
        # Standard JSON parsing
        return json.loads(body)
    except json.JSONDecodeError as json_err:
        try:
            # Fallback to YAML (YAML is a superset of JSON and is more forgiving with newlines)
            data = yaml.safe_load(body)
            # If it's just a string or not a dict, it's likely not what we want from a payload
            if isinstance(data, dict):
                logger.info("JSON parsing failed, but YAML fallback succeeded.")
                return data
            raise Exception("YAML parsed but result is not a dictionary")
        except Exception:
            # If both fail, report the original JSON error with helpful hints
            logger.error(f"JSON Parse Error: {json_err}")
            
            error_msg = f"Invalid JSON or YAML: {json_err.msg}"
            if "control character" in json_err.msg.lower():
                error_msg += ". Hint: Literal newlines and unescaped quotes are not allowed in JSON strings. You can fix this by using 'Content-Type: application/yaml' (recommended) or by escaping the prompt."
            elif "expecting value" in json_err.msg.lower():
                error_msg += ". Hint: The request body is malformed or incomplete."
            
            raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Unexpected error parsing payload: {e}")
        raise HTTPException(status_code=400, detail="Failed to parse request body")
