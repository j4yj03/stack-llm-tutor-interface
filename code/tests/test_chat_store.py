from uuid import UUID


def test_create_chat_returns_uuid(
    chat_store,
    stack_context
):
    chat_id = chat_store.create_chat(
        question_id=stack_context.question_id,
        stack_context=stack_context.dict()
    )

    assert str(UUID(chat_id)) == chat_id


def test_messages_are_stored_in_order(
    chat_store,
    stack_context
):
    chat_id = chat_store.create_chat(
        question_id=stack_context.question_id,
        stack_context=stack_context.dict()
    )

    chat_store.add_message(
        chat_id,
        "assistant",
        "Erster Hinweis"
    )
    chat_store.add_message(
        chat_id,
        "user",
        "Meine Rückfrage"
    )

    messages = chat_store.get_messages(chat_id)

    assert len(messages) == 2
    assert messages[0]["content"] == "Erster Hinweis"
    assert messages[1]["content"] == "Meine Rückfrage"


def test_hint_level_stops_at_four(
    chat_store,
    stack_context
):
    chat_id = chat_store.create_chat(
        question_id=stack_context.question_id,
        stack_context=stack_context.dict(),
        hint_level=3
    )

    assert chat_store.next_hint_level(chat_id) == 4
    assert chat_store.next_hint_level(chat_id) == 4