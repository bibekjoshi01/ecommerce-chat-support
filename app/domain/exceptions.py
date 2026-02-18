from app.domain.enums import ConversationStatus, TransitionAction


class InvalidConversationTransition(ValueError):
    def __init__(self, current: ConversationStatus, action: TransitionAction) -> None:
        super().__init__(
            f"Cannot apply action '{action.value}' from state '{current.value}'."
        )
        self.current = current
        self.action = action
