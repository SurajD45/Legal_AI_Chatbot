from fastapi import APIRouter, HTTPException, Request
from app.models import ChatRequest, ChatResponse
from app.core.retriever import get_retriever
from app.core.llm_chain import get_llm_chain
from app.core.chat_history import get_history_manager
from app.dependencies import limiter, get_rate_limit_string
from app.utils import get_logger, LegalAIException

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/query", response_model=ChatResponse)
@limiter.limit(get_rate_limit_string())
async def query_legal_assistant(request: Request, chat_request: ChatRequest):
    try:
        history_manager = get_history_manager()
        session_id = chat_request.session_id or history_manager.create_session()
        chat_history = history_manager.get_history(session_id)

        retriever = get_retriever()
        documents = retriever.hybrid_search(chat_request.query)

        llm_chain = get_llm_chain()
        answer = llm_chain.generate_answer(
            query=chat_request.query,
            documents=documents,
            chat_history=chat_history
        )

        history_manager.add_message(session_id, "user", chat_request.query)
        history_manager.add_message(session_id, "assistant", answer)

        return ChatResponse(
            answer=answer,
            sources=documents,
            session_id=session_id,
            query=chat_request.query
        )

    except LegalAIException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")
