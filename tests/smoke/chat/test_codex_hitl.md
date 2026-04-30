# Codex HITL request lifecycle smoke

1. Start the chat backend against a Codex-capable harness.
2. Create a chat and send a prompt that triggers an approval request.
3. Observe `request.opened` on `/ws/chat/{chat_id}`.
4. `POST /chat/{chat_id}/approve` with `request_id` and `decision`.
5. Verify the stream later contains `request.resolved` with the same `request_id`.
6. Send a prompt that triggers runtime user input.
7. Observe `user_input.requested`, then `POST /chat/{chat_id}/input` with answers.
8. Verify `user_input.resolved` is persisted and replayable after reconnect.

Unsupported harness check: repeat the approve/input POSTs against a Claude/OpenCode chat with an active execution; response should be rejected cleanly because no runtime request channel exists.
