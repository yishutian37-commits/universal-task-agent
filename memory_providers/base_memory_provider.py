from abc import ABC, abstractmethod

from core.state import AgentState


class BaseMemoryProvider(ABC):
    @abstractmethod
    def save_task(self, state: AgentState) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_context(self) -> dict:
        raise NotImplementedError
