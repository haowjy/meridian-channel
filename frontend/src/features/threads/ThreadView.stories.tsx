import type { Meta, StoryObj } from "@storybook/react-vite"

import { TimelineScrubber } from "@/components/storybook/TimelineScrubber"
import { THREAD_WALKTHROUGH, THREAD_WALKTHROUGH_ACTIVE_TURN_ID } from "@/features/activity-stream/examples"
import type { TimelinePlayback } from "@/lib/use-timeline-playback"

import { TurnList } from "./components/TurnList"
import { useThreadSimulator } from "./hooks/use-thread-simulator"

function ThreadScrubberStory() {
  const simulator = useThreadSimulator({
    history: THREAD_WALKTHROUGH.history,
    activeTimeline: THREAD_WALKTHROUGH.activeTimeline,
    threadId: THREAD_WALKTHROUGH.threadId,
    activeTurnId: THREAD_WALKTHROUGH_ACTIVE_TURN_ID,
    autoplay: true,
    initialSpeed: 1,
  })
  const playback: TimelinePlayback = simulator

  return (
    <div className="flex h-[44rem] w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-border bg-background">
      <div className="bg-gradient-to-b from-background from-80% to-transparent px-4 pb-6 pt-3">
        <TimelineScrubber
          playback={playback}
          markers={simulator.turnMarkers}
          statusLabel={simulator.eventLabel}
          phaseLabel={simulator.phaseLabel}
        />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4">
        <div className="py-2">
          {simulator.state.turns.length === 0 ? (
            <p className="text-sm text-muted-foreground">Waiting to load conversation history…</p>
          ) : (
            <TurnList
              turns={simulator.state.turns}
              onSwitchSibling={(targetTurnId) => {
                void simulator.store.switchSibling(targetTurnId)
              }}
            />
          )}
        </div>
      </div>

      <div className="border-t border-border/50 px-4 py-3">
        <div className="mx-auto w-full max-w-4xl rounded-xl border border-border/70 bg-card px-4 py-3 text-sm text-muted-foreground">
          Composer intentionally omitted in this migration step.
        </div>
      </div>
    </div>
  )
}

const meta = {
  title: "Features/Threads/Thread View",
  component: TurnList,
  args: {
    turns: [],
  },
  parameters: {
    layout: "fullscreen",
  },
} satisfies Meta<typeof TurnList>

export default meta
type Story = StoryObj<typeof meta>

export const Scrubber: Story = {
  render: () => <ThreadScrubberStory />,
}
