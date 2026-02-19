from uuid import UUID

AGENT_PRESENCE_CHANNEL = "agents:presence"


def conversation_channel(conversation_id: UUID) -> str:
    return f"conversation:{conversation_id}"


def agent_queue_channel(agent_id: UUID) -> str:
    return f"agent:{agent_id}:queue"
