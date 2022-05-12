from abc import ABC, abstractmethod


class BaseAction(ABC):
    def __eq__(self, other):
        raise NotImplementedError()

    def __hash__(self):
        raise NotImplementedError()


class BaseState(ABC):
    @abstractmethod
    def getCurrentPlayer(self) -> int:
        # 1 for maximiser, -1 for minimiser
        raise NotImplementedError()

    @abstractmethod
    def getPossibleActions(self) -> [BaseAction]:
        raise NotImplementedError()

    @abstractmethod
    def takeAction(self, action) -> 'BaseState':
        raise NotImplementedError()

    @abstractmethod
    def isTerminal(self) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def getReward(self) -> float:
        # only needed for terminal states
        raise NotImplementedError()

    @abstractmethod
    def __eq__(self, other):
        raise NotImplementedError()
