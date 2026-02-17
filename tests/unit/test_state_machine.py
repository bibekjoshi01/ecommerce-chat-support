import pytest

from app.domain.enums import ConversationStatus, TransitionAction
from app.domain.exceptions import InvalidConversationTransition
from app.domain.state_machine import ConversationLifecycle


def test_automated_to_agent_transition() -> None:
    next_state = ConversationLifecycle.transition(
        ConversationStatus.AUTOMATED, TransitionAction.ESCALATE_TO_AGENT
    )
    assert next_state == ConversationStatus.AGENT


def test_agent_to_closed_transition() -> None:
    next_state = ConversationLifecycle.transition(
        ConversationStatus.AGENT, TransitionAction.CLOSE_BY_AGENT
    )
    assert next_state == ConversationStatus.CLOSED


def test_idempotent_escalate_from_agent() -> None:
    next_state = ConversationLifecycle.transition(
        ConversationStatus.AGENT, TransitionAction.ESCALATE_TO_AGENT
    )
    assert next_state == ConversationStatus.AGENT


def test_invalid_transition_raises() -> None:
    with pytest.raises(InvalidConversationTransition):
        ConversationLifecycle.transition(ConversationStatus.AUTOMATED, TransitionAction.CLOSE_BY_AGENT)


def test_closed_is_read_only() -> None:
    assert ConversationLifecycle.is_read_only(ConversationStatus.CLOSED)
    assert not ConversationLifecycle.is_read_only(ConversationStatus.AUTOMATED)


def test_talk_to_agent_visibility_rules() -> None:
    assert ConversationLifecycle.should_show_talk_to_agent(ConversationStatus.AUTOMATED)
    assert not ConversationLifecycle.should_show_talk_to_agent(ConversationStatus.AGENT)
    assert not ConversationLifecycle.should_show_talk_to_agent(ConversationStatus.CLOSED)
