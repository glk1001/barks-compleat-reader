"""Tests for search_ports protocols and the InMemoryFullTextSearch fake."""

from barks_fantagraphics.search_ports import FullTextSearchPort
from barks_fantagraphics.testing.fake_search import InMemoryFullTextSearch
from barks_fantagraphics.whoosh_search_engine import TitleInfo


class TestInMemoryFullTextSearch:
    def test_satisfies_protocol(self) -> None:
        fake = InMemoryFullTextSearch()
        assert isinstance(fake, FullTextSearchPort)

    def test_find_words_returns_canned_result(self) -> None:
        expected = {"Title A": TitleInfo(fanta_vol=1)}
        fake = InMemoryFullTextSearch(find_words_results={"duck": expected})
        assert fake.find_words("duck") == expected
        assert fake.find_words("missing") == {}

    def test_find_entities_returns_canned_result(self) -> None:
        expected = {"Title B": TitleInfo(fanta_vol=2)}
        fake = InMemoryFullTextSearch(find_entities_results={("person", "Donald Duck"): expected})
        assert fake.find_entities("person", "Donald Duck") == expected
        assert fake.find_entities("person", "nobody") == {}

    def test_get_cleaned_terms(self) -> None:
        fake = InMemoryFullTextSearch(cleaned_terms=["apple", "banana"])
        assert fake.get_cleaned_terms() == ["apple", "banana"]

    def test_get_cleaned_alpha_split_terms(self) -> None:
        alpha = {"a": {"ap": ["apple"]}}
        fake = InMemoryFullTextSearch(cleaned_alpha_split_terms=alpha)
        assert fake.get_cleaned_alpha_split_terms() == alpha

    def test_get_entity_terms(self) -> None:
        fake = InMemoryFullTextSearch(entity_terms={"person": ["Donald", "Scrooge"]})
        assert fake.get_entity_terms("person") == ["Donald", "Scrooge"]
        assert fake.get_entity_terms("location") == []

    def test_get_alpha_split_entity_terms(self) -> None:
        alpha = {"d": {"do": ["Donald"]}}
        fake = InMemoryFullTextSearch(alpha_split_entity_terms={"person": alpha})
        assert fake.get_alpha_split_entity_terms("person") == alpha
        assert fake.get_alpha_split_entity_terms("location") == {}

    def test_get_all_titles(self) -> None:
        fake = InMemoryFullTextSearch(all_titles={"Title A", "Title B"})
        assert fake.get_all_titles() == {"Title A", "Title B"}

    def test_defaults_are_empty(self) -> None:
        fake = InMemoryFullTextSearch()
        assert fake.find_words("anything") == {}
        assert fake.find_entities("person", "anyone") == {}
        assert fake.get_all_titles() == set()
        assert fake.get_cleaned_terms() == []
        assert fake.get_cleaned_alpha_split_terms() == {}
        assert fake.get_entity_terms("person") == []
        assert fake.get_alpha_split_entity_terms("person") == {}
