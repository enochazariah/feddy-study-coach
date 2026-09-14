from .models import AgentRun, Conversation, Message


def get_or_create_conversation(user, conversation_id: str | None) -> Conversation:
    if conversation_id:
        # Ownership check happens here, server-side — never trust a client-supplied id blindly.
        existing = Conversation.objects.filter(id=conversation_id, user=user).first()
        if existing:
            return existing

    return Conversation.objects.create(user=user)


def get_recent_messages(conversation: Conversation, limit: int = 20):
    return list(conversation.messages.order_by("created_at")[:limit])


def save_message(conversation: Conversation, role: str, content: str) -> None:
    Message.objects.create(conversation=conversation, role=role, content=content)


def record_agent_run(
    *,
    user,
    conversation: Conversation | None,
    agent_name: str,
    status: str,
    latency_ms: int,
    error_message: str | None = None,
) -> None:
    AgentRun.objects.create(
        user=user,
        conversation=conversation,
        agent_name=agent_name,
        status=status,
        latency_ms=latency_ms,
        error_message=error_message,
    )
