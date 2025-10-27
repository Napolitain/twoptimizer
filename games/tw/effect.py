import abc


class Effect(abc.ABC):
    @abc.abstractmethod
    def gdp(self) -> float:
        pass

    @abc.abstractmethod
    def public_order(self) -> float:
        pass

    @abc.abstractmethod
    def sanitation(self) -> float:
        pass

    @abc.abstractmethod
    def food(self) -> float:
        pass
