from app.domain.enums import ConversationStatus, TransitionAction
from app.domain.exceptions import InvalidConversationTransition


class ConversationLifecycle:
    """State machine for conversation lifecycle: automated -> agent -> closed."""

    _allowed_transitions: dict[tuple[ConversationStatus, TransitionAction], ConversationStatus] = {
        (ConversationStatus.AUTOMATED, TransitionAction.ESCALATE_TO_AGENT): ConversationStatus.AGENT,
        (ConversationStatus.AGENT, TransitionAction.CLOSE_BY_AGENT): ConversationStatus.CLOSED,
    }

    @classmethod
    def transition(cls, current: ConversationStatus, action: TransitionAction) -> ConversationStatus:
        # Idempotent semantics for repeated UI actions.
        if current == ConversationStatus.AGENT and action == TransitionAction.ESCALATE_TO_AGENT:
            return ConversationStatus.AGENT
        if current == ConversationStatus.CLOSED and action == TransitionAction.CLOSE_BY_AGENT:
            return ConversationStatus.CLOSED

        next_state = cls._allowed_transitions.get((current, action))
        if not next_state:
            raise InvalidConversationTransition(current=current, action=action)
        return next_state

    @staticmethod
    def is_read_only(status: ConversationStatus) -> bool:
        return status == ConversationStatus.CLOSED

    @staticmethod
    def should_show_talk_to_agent(status: ConversationStatus) -> bool:
        return status == ConversationStatus.AUTOMATED
