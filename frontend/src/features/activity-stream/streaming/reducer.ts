import { EventType, type StreamEvent } from "@/lib/ws/types"

export type ActivityItem =
  | { type: "text"; messageId: string; content: string }
  | { type: "reasoning"; messageId: string; content: string }
  | {
      type: "tool_call"
      toolCallId: string
      name: string
      args: string
      status: "running" | "complete"
    }
  | { type: "tool_result"; toolCallId: string; content: string }
  | { type: "error"; message: string }

export interface StreamState {
  items: ActivityItem[]
  isStreaming: boolean
  error: string | null
  isCancelled: boolean
}

type StreamAction =
  | StreamEvent
  | { type: "SET_CANCELLED" }
  | { type: "RESET" }

export const initialState: StreamState = {
  items: [],
  isStreaming: false,
  error: null,
  isCancelled: false,
}

export function reducer(state: StreamState, action: StreamAction): StreamState {
  switch (action.type) {
    case "RESET":
      return initialState

    case "SET_CANCELLED":
      return {
        ...state,
        isCancelled: true,
      }

    case EventType.RUN_STARTED:
      return {
        ...state,
        isStreaming: true,
        error: null,
        isCancelled: false,
      }

    case EventType.RUN_FINISHED:
      return {
        ...state,
        isStreaming: false,
      }

    case EventType.RUN_ERROR:
      return {
        ...state,
        isStreaming: false,
        error: action.message,
      }

    case EventType.TEXT_MESSAGE_START:
      return {
        ...state,
        items: [...state.items, { type: "text", messageId: action.message_id, content: "" }],
      }

    case EventType.TEXT_MESSAGE_CONTENT:
      return {
        ...state,
        items: state.items.map((item) => {
          if (item.type !== "text" || item.messageId !== action.message_id) {
            return item
          }

          return {
            ...item,
            content: item.content + (action.delta ?? ""),
          }
        }),
      }

    case EventType.TEXT_MESSAGE_END:
      return state

    case EventType.TEXT_MESSAGE_CHUNK: {
      const messageId = action.message_id
      const delta = action.delta ?? ""

      if (!messageId) {
        return state
      }

      const matched = state.items.some(
        (item) => item.type === "text" && item.messageId === messageId,
      )

      if (matched) {
        return {
          ...state,
          items: state.items.map((item) => {
            if (item.type !== "text" || item.messageId !== messageId) {
              return item
            }

            return {
              ...item,
              content: item.content + delta,
            }
          }),
        }
      }

      if (!action.role) {
        return state
      }

      return {
        ...state,
        items: [...state.items, { type: "text", messageId, content: delta }],
      }
    }

    case EventType.REASONING_MESSAGE_START:
      return {
        ...state,
        items: [
          ...state.items,
          { type: "reasoning", messageId: action.message_id, content: "" },
        ],
      }

    case EventType.REASONING_MESSAGE_CONTENT:
      return {
        ...state,
        items: state.items.map((item) => {
          if (item.type !== "reasoning" || item.messageId !== action.message_id) {
            return item
          }

          return {
            ...item,
            content: item.content + (action.delta ?? ""),
          }
        }),
      }

    case EventType.REASONING_MESSAGE_END:
      return state

    case EventType.REASONING_MESSAGE_CHUNK: {
      const messageId = action.message_id
      const delta = action.delta ?? ""

      if (!messageId) {
        return state
      }

      const matched = state.items.some(
        (item) => item.type === "reasoning" && item.messageId === messageId,
      )

      if (matched) {
        return {
          ...state,
          items: state.items.map((item) => {
            if (item.type !== "reasoning" || item.messageId !== messageId) {
              return item
            }

            return {
              ...item,
              content: item.content + delta,
            }
          }),
        }
      }

      return {
        ...state,
        items: [...state.items, { type: "reasoning", messageId, content: delta }],
      }
    }

    case EventType.TOOL_CALL_START:
      return {
        ...state,
        items: [
          ...state.items,
          {
            type: "tool_call",
            toolCallId: action.tool_call_id,
            name: action.tool_call_name,
            args: "",
            status: "running",
          },
        ],
      }

    case EventType.TOOL_CALL_ARGS:
      return {
        ...state,
        items: state.items.map((item) => {
          if (item.type !== "tool_call" || item.toolCallId !== action.tool_call_id) {
            return item
          }

          return {
            ...item,
            args: item.args + (action.delta ?? ""),
          }
        }),
      }

    case EventType.TOOL_CALL_END:
      return {
        ...state,
        items: state.items.map((item) => {
          if (item.type !== "tool_call" || item.toolCallId !== action.tool_call_id) {
            return item
          }

          return {
            ...item,
            status: "complete",
          }
        }),
      }

    case EventType.TOOL_CALL_CHUNK: {
      const toolCallId = action.tool_call_id
      const delta = action.delta ?? ""

      if (!toolCallId) {
        return state
      }

      const matched = state.items.some(
        (item) => item.type === "tool_call" && item.toolCallId === toolCallId,
      )

      if (matched) {
        return {
          ...state,
          items: state.items.map((item) => {
            if (item.type !== "tool_call" || item.toolCallId !== toolCallId) {
              return item
            }

            return {
              ...item,
              args: item.args + delta,
            }
          }),
        }
      }

      if (!action.tool_call_name) {
        return state
      }

      return {
        ...state,
        items: [
          ...state.items,
          {
            type: "tool_call",
            toolCallId,
            name: action.tool_call_name,
            args: delta,
            status: "running",
          },
        ],
      }
    }

    case EventType.TOOL_CALL_RESULT:
      return {
        ...state,
        items: [
          ...state.items,
          {
            type: "tool_result",
            toolCallId: action.tool_call_id,
            content: action.content,
          },
        ],
      }

    case EventType.CUSTOM:
      return state

    default:
      return state
  }
}
