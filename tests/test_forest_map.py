import pytest
from pydantic import ValidationError

from forest_bot.domain import ScopeLevel
from forest_bot.domain.forest_map import ForestMap, UnknownPlace, forest_map


def test_the_map_file_loads_with_every_place():
    places = forest_map.places
    assert places["forest"].level == ScopeLevel.FOREST
    assert places["coniferous"].level == ScopeLevel.PART
    assert places["under_willow"].level == ScopeLevel.MITTEN
    assert forest_map.mittens["under_willow"].parts == ["deciduous", "river"]
    assert len(places) == 1 + 3 + 8


def test_an_id_not_on_the_map_is_an_unknown_place():
    assert forest_map.place("under_oak").name == "Під дубом"
    with pytest.raises(UnknownPlace):
        forest_map.place("under_birch")


def test_a_mitten_in_an_unknown_part_is_rejected():
    with pytest.raises(ValidationError, match="unknown parts"):
        ForestMap.model_validate(
            {"forest": "Ліс", "parts": {}, "mittens": {"m": {"name": "М", "parts": ["nowhere"]}}}
        )


def test_a_place_id_used_twice_is_rejected():
    with pytest.raises(ValidationError, match="used twice"):
        ForestMap.model_validate(
            {"forest": "Ліс", "parts": {"x": "Х"}, "mittens": {"x": {"name": "М", "parts": []}}}
        )


def test_every_place_is_described_for_the_llm():
    description = forest_map.describe()
    for place_id in forest_map.places:
        assert f"- {place_id}: " in description
    assert "Під вербою (a mitten in: Листяний ліс, Біля річки)" in description
    assert "На узліссі (a mitten in: no part)" in description
