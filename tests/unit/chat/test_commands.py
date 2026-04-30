from meridian.lib.chat.commands import (
    COMMAND_PROMPT,
    COMMAND_SWAP_MODEL,
    SUPPORTED_COMMAND_TYPES,
    ChatCommand,
    CommandResult,
)


def test_chat_command_shape():
    command = ChatCommand(COMMAND_PROMPT, "cmd1", "c1", "now", {"text": "hi"})

    assert command.type == "prompt"
    assert command.payload["text"] == "hi"


def test_deferred_commands_are_schema_recognized():
    assert COMMAND_SWAP_MODEL in SUPPORTED_COMMAND_TYPES


def test_command_result_rejected():
    assert CommandResult("rejected", "nope").error == "nope"
