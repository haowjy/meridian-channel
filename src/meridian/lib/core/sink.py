"""Shared output sink protocol, no-op sink, and composite fan-out sink."""


from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class OutputSink(Protocol):
    def result(self, payload: Any) -> None: ...

    def status(self, message: str) -> None: ...

    def warning(self, message: str) -> None: ...

    def error(self, message: str, exit_code: int = 1) -> None: ...

    def heartbeat(self, message: str) -> None: ...

    def event(self, payload: dict[str, Any]) -> None: ...


class NullSink:
    def result(self, payload: Any) -> None:
        _ = payload

    def status(self, message: str) -> None:
        _ = message

    def warning(self, message: str) -> None:
        _ = message

    def error(self, message: str, exit_code: int = 1) -> None:
        _ = (message, exit_code)

    def heartbeat(self, message: str) -> None:
        _ = message

    def event(self, payload: dict[str, Any]) -> None:
        _ = payload

    def flush(self) -> None:
        return


class CompositeSink:
    """Fan-out to multiple sinks.

    Delivers each method call to every child sink in order.  Individual
    sink errors are suppressed so one failing sink cannot break the others.
    """

    def __init__(self, *sinks: OutputSink) -> None:
        self._sinks = sinks

    def result(self, payload: Any) -> None:
        for sink in self._sinks:
            try:
                sink.result(payload)
            except Exception:
                pass

    def status(self, message: str) -> None:
        for sink in self._sinks:
            try:
                sink.status(message)
            except Exception:
                pass

    def warning(self, message: str) -> None:
        for sink in self._sinks:
            try:
                sink.warning(message)
            except Exception:
                pass

    def error(self, message: str, exit_code: int = 1) -> None:
        for sink in self._sinks:
            try:
                sink.error(message, exit_code)
            except Exception:
                pass

    def heartbeat(self, message: str) -> None:
        for sink in self._sinks:
            try:
                sink.heartbeat(message)
            except Exception:
                pass

    def event(self, payload: dict[str, Any]) -> None:
        for sink in self._sinks:
            try:
                sink.event(payload)
            except Exception:
                pass

    def flush(self) -> None:
        for sink in self._sinks:
            try:
                flush_fn = getattr(sink, "flush", None)
                if callable(flush_fn):
                    flush_fn()
            except Exception:
                pass
