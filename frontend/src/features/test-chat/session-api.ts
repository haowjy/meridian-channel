export interface TestChatSessionInfo {
  spawn_id: string
  harness: string
  model: string
  chat_id: string
  session_log_path: string
  capabilities_url: string
}

export class TestChatApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = "TestChatApiError"
  }
}

export async function fetchTestChatSession(): Promise<TestChatSessionInfo> {
  const response = await fetch("/api/test-chat/session", {
    headers: { "Content-Type": "application/json" },
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = (await response.json()) as { detail?: string; message?: string }
      detail = body.detail ?? body.message ?? detail
    } catch {
      // Keep status text for non-JSON error bodies.
    }
    throw new TestChatApiError(response.status, `${response.status} ${detail}`)
  }

  return (await response.json()) as TestChatSessionInfo
}
