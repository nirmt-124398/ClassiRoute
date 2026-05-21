import httpx
from anthropic import APIStatusError
from anthropic import AsyncAnthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["keys-anthropic"])

VERIFY_MODEL = "claude-3-haiku-20240307"


class AnthropicModelsRequest(BaseModel):
    api_key: str = Field(min_length=1)


class AnthropicModelsResponse(BaseModel):
    models: list[str]


@router.post("/keys/anthropic/verify")
async def verify_anthropic_key(payload: dict):
    api_key = payload.get("api_key", "")
    if not api_key:
        return {"valid": False, "error": "API key is required"}

    try:
        client = AsyncAnthropic(api_key=api_key)
        await client.messages.create(
            model=VERIFY_MODEL,
            max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
        )
        return {"valid": True}
    except APIStatusError as e:
        if e.response and e.response.status_code == 401:
            return {"valid": False, "error": "Invalid API key (401 Unauthorized)"}
        return {"valid": False, "error": f"API error: {e}"}
    except httpx.HTTPStatusError as e:
        return {"valid": False, "error": f"HTTP error: {e}"}
    except Exception as e:
        return {"valid": False, "error": str(e)}


@router.post("/keys/anthropic/models", response_model=AnthropicModelsResponse)
async def list_anthropic_models(payload: AnthropicModelsRequest):
    try:
        client = AsyncAnthropic(api_key=payload.api_key)
        models: list[str] = []
        async for model in client.models.list():
            model_id = getattr(model, "id", None)
            if model_id:
                models.append(model_id)
    except APIStatusError as e:
        status_code = e.response.status_code if e.response else 502
        if status_code == 401:
            raise HTTPException(
                status_code=401, detail="Invalid API key (401 Unauthorized)"
            ) from e
        raise HTTPException(status_code=status_code, detail=f"Anthropic API error: {e}") from e
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"HTTP error: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Anthropic API error: {e}") from e

    models = sorted(set(models))
    if not models:
        raise HTTPException(
            status_code=502,
            detail="No models returned from Anthropic. Check your API key and account access.",
        )

    return AnthropicModelsResponse(models=models)
