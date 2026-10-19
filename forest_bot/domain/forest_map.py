import tomllib
from functools import cached_property
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from forest_bot.domain.enums import ScopeLevel
from forest_bot.settings import settings

FOREST_ID = "forest"


class UnknownPlace(LookupError):
    """A place id that is not on the map, e.g. a button sent before the map changed."""


class Mitten(BaseModel):
    name: str
    parts: list[str]


class Place(BaseModel):
    """Anything a document can apply to: the whole forest, a part of it or a mitten."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    level: ScopeLevel


class ForestMap(BaseModel):
    forest: str
    parts: dict[str, str]  # id → name
    mittens: dict[str, Mitten]  # id → mitten

    @model_validator(mode="after")
    def _check_ids(self) -> Self:
        ids = [FOREST_ID, *self.parts, *self.mittens]
        if len(ids) != len(set(ids)):
            raise ValueError(f"a place id is used twice: {ids}")
        for mitten_id, mitten in self.mittens.items():
            if unknown := set(mitten.parts) - self.parts.keys():
                raise ValueError(f"mitten {mitten_id!r} lies in unknown parts {unknown}")
        return self

    @cached_property
    def places(self) -> dict[str, Place]:
        """Every place by id: the forest, then parts, then mittens."""
        places = [Place(id=FOREST_ID, name=self.forest, level=ScopeLevel.FOREST)]
        places += [Place(id=i, name=n, level=ScopeLevel.PART) for i, n in self.parts.items()]
        places += [
            Place(id=i, name=m.name, level=ScopeLevel.MITTEN) for i, m in self.mittens.items()
        ]
        return {place.id: place for place in places}

    def place(self, place_id: str) -> Place:
        try:
            return self.places[place_id]
        except KeyError:
            raise UnknownPlace(place_id) from None

    def describe(self) -> str:
        """The map for an LLM prompt: one line per place, `- id: name (what it is)`."""
        lines = [f"- {FOREST_ID}: {self.forest} (the whole forest)"]
        lines += [f"- {i}: {name} (a part of the forest)" for i, name in self.parts.items()]
        for mitten_id, mitten in self.mittens.items():
            parts = ", ".join(self.parts[p] for p in mitten.parts) or "no part"
            lines.append(f"- {mitten_id}: {mitten.name} (a mitten in: {parts})")
        return "\n".join(lines)

    @classmethod
    def load(cls, path: Path) -> ForestMap:
        return cls.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))


forest_map = ForestMap.load(settings.forest_map_path)
