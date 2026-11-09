"""Build-only assembly of Attila placement rules and scoped economics."""

from games.tw.attila.builder import BinaryBuilder
from games.tw.attila.context import AttilaContext
from games.tw.attila.economy import Economy
from games.tw.attila.modifiers import technology_profile
from games.tw.attila.province import Province
from games.tw.attila.scenario import Scenario


class Construction:
    """Own one isolated compilation; shared solver services execute its model."""

    def __init__(
        self,
        objective="income",
        adjacency=None,
        technologies=None,
        scenario=None,
        *,
        context: AttilaContext,
    ):
        if objective not in ("wealth", "income"):
            raise ValueError("Choose the wealth or income objective")
        self.context = context.for_model()
        self.provinces: list[Province] = []
        self.objective_mode = objective
        self.technologies = None if technologies is None else frozenset(technologies)
        self.technology_profile = None
        if getattr(self.context.instance, "faction", None) is not None:
            scenario_data = scenario.to_dict() if isinstance(scenario, Scenario) else scenario or {}
            self.technology_profile = technology_profile(
                self.context.instance,
                technologies,
                scenario_data.get("technology_effects", True),
            )
            if self.technology_profile is not None and technologies is not None:
                self.technologies = frozenset(self.technology_profile["active"])
        self.scenario = scenario
        self.adjacency = adjacency
        self.economy: Economy | None = None
        self.builder = BinaryBuilder()
        self.builder.technologies = self.technologies
        self.builder.disabled_technologies = (
            set(self.technology_profile["disabled_legacy"]) if self.technology_profile else set()
        )
        self.builder.require_income_metadata = objective == "income"
        self.context.builder = self.builder

    def add_province(self, province: Province) -> None:
        province.context = self.context
        for region in province.regions:
            region.context = self.context
        self.provinces.append(province)

    def add_objective(self) -> None:
        self.economy = Economy(
            self.provinces,
            self.adjacency,
            self.scenario,
            self.technology_profile,
            context=self.context,
        )
        self.economy.catalogue_exclusions = self.builder.catalogue_exclusions
        self.economy.install_constraints(self.builder)
        self.builder.add_objective_terms(
            self.economy.compile(self.economy.objective(self.objective_mode), self.builder)
        )
        if self.objective_mode == "income":
            self.builder.compact_economy = self.economy
