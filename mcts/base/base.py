from abc import ABC, abstractmethod


class BaseAction(ABC):
    def __eq__(self, other):
        raise NotImplementedError()

    def __hash__(self):
        raise NotImplementedError()


class BaseState(ABC):
    @abstractmethod
    def get_current_player(self) -> int:
        # 1 for maximiser, -1 for minimiser
        raise NotImplementedError()

    @abstractmethod
    def get_possible_actions(self) -> []:
        raise NotImplementedError()

    @abstractmethod
    def take_action(self, action) -> 'BaseState':
        raise NotImplementedError()

    @abstractmethod
    def is_terminal(self) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def get_reward(self) -> float:
        # only needed for terminal states
        raise NotImplementedError()
