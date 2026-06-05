from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import Response

from app.models import ChatRequest, ChatResponse
from app.core.retriever import get_retriever
from app.core.llm_chain import get_llm_chain
from app.core.chat_history import get_history_manager
from app.core.query_condenser import get_query_condenser
from app.core.context_expander import get_context_expander
from app.dependencies import limiter, get_rate_limit_string, get_current_user
from app.utils import get_logger, LegalAIException, InvalidSessionError

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


# OPTIONS (CORS preflight)
@router.options("/query")
async def options_query():
    return Response(status_code=200)


# RESTORE last session (protected)
@router.get("/session/latest")
async def get_latest_session(user_id: str = Depends(get_current_user)):
    try:
        history_manager = get_history_manager()
        session = history_manager.get_latest_session(user_id)

        if not session:
            return {"session_id": None, "history": []}

        return session

    except Exception as e:
        logger.error("get_latest_session_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to load history")


# QUERY legal assistant (protected)
@router.post("/query", response_model=ChatResponse)
@limiter.limit(get_rate_limit_string())
async def query_legal_assistant(
    request: Request,
    chat_request: ChatRequest,
    user_id: str = Depends(get_current_user),
):
    try:
        history_manager = get_history_manager()

        # ── Session management ────────────────────────────────────────────────
        if chat_request.session_id is None:
            session_id = history_manager.create_session(user_id=user_id)
        else:
            session_id = chat_request.session_id

        chat_history = history_manager.get_history(
            user_id=user_id,
            session_id=session_id,
        )

        # ── Phase 9A: Query Condensation ──────────────────────────────────────
        # For contextual follow-ups (e.g. "give me definition then"), rewrite
        # the query into a standalone search query using lightweight LLM.
        # Standalone queries skip LLM entirely (0ms overhead).
        condenser = get_query_condenser()
        condensation_result = condenser.condense(
            query=chat_request.query,
            chat_history=chat_history,
        )
        search_query = condensation_result["search_query"]

        if condensation_result["condensed"]:
            logger.info(
                "query_condensed",
                original=condensation_result["original_query"],
                rewritten=search_query,
                rewrite_ms=condensation_result["rewrite_ms"],
            )

        # ── Retrieval ─────────────────────────────────────────────────────────
        retriever = get_retriever()
        documents = retriever.hybrid_search(search_query)

        # ── Phase 9B: Context Expansion ───────────────────────────────────────
        # Add semantically related IPC sections to the document list.
        # Runs AFTER retrieval and BEFORE the LLM chain — fully decoupled.
        expander = get_context_expander()
        documents = expander.expand(documents)

        # ── LLM Generation ────────────────────────────────────────────────────
        # Always pass the original (user-facing) query to the LLM, not the
        # condensed search query, so the answer remains grounded to what
        # the user actually asked.
        llm_chain = get_llm_chain()
        answer = llm_chain.generate_answer(
            query=chat_request.query,
            documents=documents,
            chat_history=chat_history,
        )

        # ── Persist conversation turn ─────────────────────────────────────────
        history_manager.add_message(
            user_id=user_id,
            session_id=session_id,
            role="user",
            content=chat_request.query,
        )
        history_manager.add_message(
            user_id=user_id,
            session_id=session_id,
            role="assistant",
            content=answer,
        )

        return ChatResponse(
            answer=answer,
            sources=documents,
            session_id=session_id,
            query=chat_request.query,
        )

    except InvalidSessionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except LegalAIException as e:
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.error("chat_endpoint_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")
