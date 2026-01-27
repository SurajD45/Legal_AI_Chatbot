from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.models import ChatRequest, ChatResponse
from app.core.retriever import get_retriever
from app.core.llm_chain import get_llm_chain
from app.core.chat_history import get_history_manager
from app.dependencies import limiter, get_rate_limit_string
from app.utils import get_logger, LegalAIException, InvalidSessionError

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


# OPTIONS (CORS preflight)
@router.options("/query")
async def options_query():
    return Response(status_code=200)


# NEW: restore last session
@router.get("/session/latest")
async def get_latest_session(user_id: str):
    try:
        history_manager = get_history_manager()
        session = history_manager.get_latest_session(user_id)

        if not session:
            return {"session_id": None, "history": []}

        return session

    except Exception as e:
        logger.error("get_latest_session_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to load history")


@router.post("/query", response_model=ChatResponse)
@limiter.limit(get_rate_limit_string())
async def query_legal_assistant(request: Request, chat_request: ChatRequest):
    try:
        history_manager = get_history_manager()

        if chat_request.session_id is None:
            session_id = history_manager.create_session(
                user_id=chat_request.user_id
            )
        else:
            session_id = chat_request.session_id

        chat_history = history_manager.get_history(
            user_id=chat_request.user_id,
            session_id=session_id,
        )

        retriever = get_retriever()
        documents = retriever.hybrid_search(chat_request.query)

        llm_chain = get_llm_chain()
        answer = llm_chain.generate_answer(
            query=chat_request.query,
            documents=documents,
            chat_history=chat_history,
        )

        history_manager.add_message(
            user_id=chat_request.user_id,
            session_id=session_id,
            role="user",
            content=chat_request.query,
        )
        history_manager.add_message(
            user_id=chat_request.user_id,
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
