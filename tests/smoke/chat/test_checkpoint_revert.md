# Chat checkpoint revert smoke

1. In a disposable git repo, start the chat backend with that repo as project root.
2. Create a chat and run a turn that changes a tracked file.
3. Verify `turn.completed` is followed by `checkpoint.created` and the payload has `commit_sha`.
4. Make another controlled edit to the same file.
5. `POST /chat/{chat_id}/revert` with the checkpoint `commit_sha`.
6. Verify the file content matches the checkpoint commit and `checkpoint.reverted` is persisted/replayable.
7. Delete `chats/{chat_id}/index.sqlite3`, restart/recover, and verify queryability is restored from `history.jsonl`.
