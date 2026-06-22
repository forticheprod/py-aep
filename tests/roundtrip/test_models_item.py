"""Tests for Item model parsing."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import get_comp

from py_aep import parse as parse_aep
from py_aep.enums import Label
from py_aep.models.items.composition import CompItem
from py_aep.models.items.footage import FootageItem
from py_aep.models.project import Project
from py_aep.models.sources.file import FileSource

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "item"
COMP_SAMPLES_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "composition"
)


class TestRoundtripItemLabel:
    """Roundtrip tests for Item.label."""

    def test_modify_item_label(self, tmp_path: Path) -> None:
        project = parse_aep(COMP_SAMPLES_DIR / "bgColor.aep").project
        comp = get_comp(project, "bgColor_custom")
        original_label = comp.label

        comp.label = Label.FUCHSIA
        assert comp.label != original_label
        out = tmp_path / "modified_label.aep"
        project.save(out)

        project2 = parse_aep(out).project
        comp2 = get_comp(project2, "bgColor_custom")
        assert comp2.label == Label.FUCHSIA


class TestRoundtripItemComment:
    """Roundtrip tests for Item.comment."""

    def test_modify_item_comment(self, tmp_path: Path) -> None:
        project = parse_aep(COMP_SAMPLES_DIR / "bgColor.aep").project
        comp = get_comp(project, "bgColor_custom")

        comp.comment = "roundtrip item comment"
        out = tmp_path / "modified_comment.aep"
        project.save(out)

        project2 = parse_aep(out).project
        comp2 = get_comp(project2, "bgColor_custom")
        assert comp2.comment == "roundtrip item comment"


class TestRoundtripItemName:
    """Roundtrip tests for Item.name."""

    def test_modify_item_name(self, tmp_path: Path) -> None:
        project = parse_aep(COMP_SAMPLES_DIR / "bgColor.aep").project
        comp = get_comp(project, "bgColor_custom")

        comp.name = "Renamed Composition"
        out = tmp_path / "modified_name.aep"
        project.save(out)

        project2 = parse_aep(out).project
        comp2 = get_comp(project2, "Renamed Composition")
        assert comp2.name == "Renamed Composition"


class TestProxySource:
    """Tests for AVItem.use_proxy and AVItem.proxy_source."""

    @pytest.fixture()
    def proxy_project(self) -> Project:
        return parse_aep(SAMPLES_DIR / "proxy.aep").project

    def _find(
        self,
        project: Project,
        name: str,
        cls: type,
    ) -> CompItem | FootageItem:
        return next(
            i
            for i in project.items.values()
            if getattr(i, "name", "") == name and isinstance(i, cls)
        )

    def test_footage_use_proxy_false(self, proxy_project: Project) -> None:
        item = self._find(proxy_project, "proxy_disabled", FootageItem)
        assert item.use_proxy is False

    def test_footage_use_proxy_true(self, proxy_project: Project) -> None:
        item = self._find(proxy_project, "proxy_enabled", FootageItem)
        assert item.use_proxy is True

    def test_footage_proxy_source_exists(self, proxy_project: Project) -> None:
        for name in ("proxy_disabled", "proxy_enabled"):
            item = self._find(proxy_project, name, FootageItem)
            assert item.proxy_source is not None
            assert isinstance(item.proxy_source, FileSource)

    def test_footage_no_proxy_source(self, proxy_project: Project) -> None:
        item = self._find(proxy_project, "no_proxy", FootageItem)
        assert item.use_proxy is False
        assert item.proxy_source is None

    def test_comp_use_proxy_true(self, proxy_project: Project) -> None:
        item = self._find(proxy_project, "proxy_enabled", CompItem)
        assert item.use_proxy is True

    def test_comp_proxy_source_exists(self, proxy_project: Project) -> None:
        item = self._find(proxy_project, "proxy_disabled", CompItem)
        assert item.proxy_source is not None
        assert isinstance(item.proxy_source, FileSource)

    def test_comp_no_proxy_source(self, proxy_project: Project) -> None:
        for name in ("layers", "no_proxy"):
            item = self._find(proxy_project, name, CompItem)
            assert item.use_proxy is False
            assert item.proxy_source is None

    def test_roundtrip_use_proxy(self, proxy_project: Project, tmp_path: Path) -> None:
        item = self._find(proxy_project, "proxy_enabled", FootageItem)
        item.use_proxy = False
        out = tmp_path / "proxy_modified.aep"
        proxy_project.save(out)

        project2 = parse_aep(out).project
        item2 = next(
            i
            for i in project2.items.values()
            if getattr(i, "name", "") == "proxy_enabled" and isinstance(i, FootageItem)
        )
        assert item2.use_proxy is False
