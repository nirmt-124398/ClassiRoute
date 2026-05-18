import json
import logging
import time
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_virtual_key
from core.dispatcher import dispatch_stream, dispatch_sync, DISPATCH_TIMEOUT
from core.router import route_prompt, TIER_NAMES
from db.database import get_db
from db.models import VirtualKey
from db import crud
from services.telemetry import capture_request, capture_error
from core.dependencies import rate_limit_chat

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    background_tasks: BackgroundTasks,
    virtual_key: VirtualKey = Depends(get_virtual_key),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(rate_limit_chat),
):
    body = await request.json()
    messages = body.get("messages", [])
    stream = body.get("stream", False)

    prompt = ""
    for message in reversed(messages):
        if message.get("role") == "user":
            prompt = message.get("content", "")
            break

    routing = route_prompt(prompt)
    start = time.time()

    if stream:
        async def stream_generator():
            usage = {"input_tokens": None, "output_tokens": None}
            status = "success"
            error_msg = None
            model_used = None
            routing_ms = 0
            dispatch_ms = 0

            routing_start = time.time()
            routing_result = route_prompt(prompt)
            routing_ms = int((time.time() - routing_start) * 1000)
            logger.info("routing: tier=%s conf=%.2f time=%dms",
                        routing_result["tier_name"], routing_result["confidence"], routing_ms)

            dispatch_start = time.time()
            try:
                # Build cascading fallback chain: 2→[2,1,0], 1→[1,0], 0→[0]
                original_tier = routing["tier"]
                attempts = list(range(original_tier, -1, -1))
                for attempt in attempts:
                    try:
                        stream_obj, model_used = await dispatch_stream(
                            messages, virtual_key, attempt
                        )
                        if attempt != original_tier:
                            routing["tier"] = attempt
                            routing["tier_name"] = TIER_NAMES.get(attempt, "weak")
                            routing["rerouted"] = True
                            routing["fallback_reason"] = f"Tier {original_tier} ({TIER_NAMES.get(original_tier, 'unknown')}) failed, cascaded to tier {attempt}"
                        first = True
                        async for chunk in stream_obj:
                            if chunk.usage is not None:
                                usage = {
                                    "input_tokens": chunk.usage.prompt_tokens,
                                    "output_tokens": chunk.usage.completion_tokens,
                                }
                            if first:
                                chunk_dict = chunk.model_dump()
                                chunk_dict["x-llmrouter"] = routing
                                yield f"data: {json.dumps(chunk_dict)}\n\n"
                                first = False
                            else:
                                yield f"data: {chunk.model_dump_json()}\n\n"
                        yield "data: [DONE]\n\n"
                        break
                    except TimeoutError as e:
                        logger.warning("Dispatch timeout on tier %d: %s", attempt, e)
                        if attempt > 0:
                            continue
                        status = "timeout"
                        error_msg = str(e)
                        routing["fallback_reason"] = f"All tiers failed (original: tier {original_tier})"
                        yield f"data: {{\"error\": \"Request timed out after {DISPATCH_TIMEOUT}s. Please try again.\"}}\n\n"
                        break
                    except Exception as e:
                        logger.error("Dispatch error on tier %d: %s", attempt, e)
                        status = "error"
                        error_msg = str(e)
                        if attempt > 0:
                            continue
                        routing["fallback_reason"] = f"All tiers failed (original: tier {original_tier})"
                        yield f"data: {{\"error\": \"Service unavailable. Please try again.\"}}\n\n"
                        break
            except Exception as e:
                if status == "success":
                    status = "error"
                    error_msg = str(e)
                capture_error(str(virtual_key.user_id), str(e), {"tier": routing["tier"], "stream": True})
                if status != "timeout":
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                dispatch_ms = int((time.time() - dispatch_start) * 1000)
                logger.info("dispatch: tier=%s model=%s time=%dms status=%s",
                            routing["tier_name"], model_used or "unknown", dispatch_ms, status)
                latency_ms = int((time.time() - start) * 1000)
                background_tasks.add_task(
                    _log, db, virtual_key, prompt, routing,
                    model_used, usage, latency_ms, status, error_msg,
                    routing_ms, dispatch_ms
                )

        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    routing_start = time.time()
    routing_result = route_prompt(prompt)
    routing_ms = int((time.time() - routing_start) * 1000)
    logger.info("routing: tier=%s conf=%.2f time=%dms",
                routing_result["tier_name"], routing_result["confidence"], routing_ms)

    model_used = None
    dispatch_start = time.time()
    original_tier = routing["tier"]
    attempts = list(range(original_tier, -1, -1))
    for attempt in attempts:
        try:
            response, model_used = await dispatch_sync(
                messages, virtual_key, attempt
            )
            if attempt != original_tier:
                routing["tier"] = attempt
                routing["tier_name"] = TIER_NAMES.get(attempt, "weak")
                routing["rerouted"] = True
                routing["fallback_reason"] = f"Tier {original_tier} ({TIER_NAMES.get(original_tier, 'unknown')}) failed, cascaded to tier {attempt}"
            break
        except (TimeoutError, Exception) as e:
            logger.warning("Dispatch %s on tier %d: %s",
                           "timeout" if isinstance(e, TimeoutError) else "error", attempt, e)
            if attempt > 0:
                continue
            dispatch_ms = int((time.time() - dispatch_start) * 1000)
            latency_ms = int((time.time() - start) * 1000)
            routing["fallback_reason"] = f"All tiers failed (original: tier {original_tier})"
            background_tasks.add_task(
                _log, db, virtual_key, prompt, routing, model_used,
                {"input_tokens": None, "output_tokens": None},
                latency_ms, "timeout" if isinstance(e, TimeoutError) else "error",
                str(e), routing_ms, dispatch_ms
            )
            status_code = 504 if isinstance(e, TimeoutError) else 502
            raise HTTPException(status_code=status_code, detail=str(e))

    dispatch_ms = int((time.time() - dispatch_start) * 1000)
    latency_ms = int((time.time() - start) * 1000)
    result = response.model_dump()
    result["x-llmrouter"] = routing
    background_tasks.add_task(
        _log, db, virtual_key, prompt, routing, model_used,
        {
            "input_tokens": response.usage.prompt_tokens if response.usage else None,
            "output_tokens": response.usage.completion_tokens if response.usage else None,
        },
        latency_ms, "success", None, routing_ms, dispatch_ms
    )
    return result


async def _log(
    db: AsyncSession,
    virtual_key: VirtualKey,
    prompt: str,
    routing: dict,
    model_used: str | None,
    usage: dict,
    latency_ms: int,
    status: str,
    error_msg: str | None,
    routing_ms: int | None = None,
    dispatch_ms: int | None = None,
):
    model_name = model_used or "unknown"

    await crud.log_request(
        db,
        virtual_key_id=virtual_key.id,
        user_id=virtual_key.user_id,
        prompt_preview=prompt[:200],
        prompt_length=len(prompt),
        tier_assigned=routing["tier"],
        confidence=routing["confidence"],
        model_used=model_name,
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        latency_ms=latency_ms,
        cost_estimate_usd=_estimate_cost(model_name, usage),
        status=status,
        error_message=error_msg,
    )

    await crud.touch_key(db, key_id=virtual_key.id)

    capture_request(
        user_id=str(virtual_key.user_id),
        properties={
            "tier_assigned": routing["tier"],
            "tier_name": routing["tier_name"],
            "confidence": routing["confidence"],
            "model_used": model_name,
            "latency_ms": latency_ms,
            "routing_ms": routing_ms,
            "dispatch_ms": dispatch_ms,
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "status": status,
            "prompt_length": len(prompt)
        }
    )


def _estimate_cost(model: str, usage: dict) -> float:
    total_tokens = (usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0)
    return round(total_tokens * 0.000002, 6)
