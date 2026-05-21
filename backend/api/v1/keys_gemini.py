import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from google import genai
from google.genai import types as genai_types

router = APIRouter(tags=["keys-gemini"])

VERIFY_MODEL = "gemini-2.0-flash-lite"


class GeminiModelsRequest(BaseModel):
    api_key: str = Field(min_length=1)


class GeminiModelsResponse(BaseModel):
    models: list[str]


@router.post("/keys/gemini/verify")
async def verify_gemini_key(payload: dict):
    api_key = payload.get("api_key", "")
    if not api_key:
        return {"valid": False, "error": "API key is required"}

    try:
        client = genai.Client(api_key=api_key)
        await client.aio.models.generate_content(
            model=VERIFY_MODEL,
            contents="ping",
            config=genai_types.GenerateContentConfig(
                max_output_tokens=1,
            ),
        )
        return {"valid": True}
    except httpx.HTTPStatusError as e:
        return {"valid": False, "error": f"HTTP error: {e}"}
    except Exception as e:
        return {"valid": False, "error": str(e)}


@router.post("/keys/gemini/models", response_model=GeminiModelsResponse)
async def list_gemini_models(payload: GeminiModelsRequest):
    try:
        client = genai.Client(api_key=payload.api_key)
        pager = await client.aio.models.list()
        models: list[str] = []
        async for model in pager:
            name = getattr(model, "name", None)
            if not name:
                continue
            actions = getattr(model, "supported_actions", None)
            if actions and "generateContent" not in actions:
                continue
            # Strip "models/" prefix — SDK returns "models/gemini-2.0-flash"
            clean = name.removeprefix("models/")
            models.append(clean)
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code if e.response else 502
        if status_code == 401:
            raise HTTPException(
                status_code=401, detail="Invalid API key (401 Unauthorized)"
            ) from e
        raise HTTPException(status_code=status_code, detail=f"Gemini API error: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gemini API error: {e}") from e

    models = sorted(set(models))
    if not models:
        raise HTTPException(
            status_code=502,
            detail="No models returned from Gemini. Check your API key and account access.",
        )

    return GeminiModelsResponse(models=models)
