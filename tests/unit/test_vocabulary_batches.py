"""Tests for curated vocabulary batch loading."""
from pathlib import Path

import pytest

from word_learn.services.vocabulary_batches import (
    VocabularyEntry,
    load_vocabulary_entries,
    resolve_batches_path,
    total_batches,
)


def test_load_vocabulary_entries(tmp_path: Path):
    course_file = tmp_path / "course.tsv"
    course_file.write_text(
        "# comment\n"
        "batch\tlevel\tnl\ten\n"
        "1\tA0\thallo\thello\n"
        "2\tA1\tde fiets\tbicycle\n",
        encoding="utf-8",
    )

    assert load_vocabulary_entries(course_file) == [
        VocabularyEntry(batch=1, level="A0", nl="hallo", en="hello"),
        VocabularyEntry(batch=2, level="A1", nl="de fiets", en="bicycle"),
    ]


def test_load_vocabulary_entries_rejects_bad_columns(tmp_path: Path):
    course_file = tmp_path / "course.tsv"
    course_file.write_text("1\tA0\thallo\n", encoding="utf-8")

    with pytest.raises(ValueError, match="expected 4 tab-separated columns"):
        load_vocabulary_entries(course_file)


def test_total_batches():
    entries = [
        VocabularyEntry(batch=1, level="A0", nl="hallo", en="hello"),
        VocabularyEntry(batch=3, level="A1", nl="gaan", en="to go"),
    ]

    assert total_batches(entries) == 3


def test_resolve_batches_path_prefers_current_working_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    batches_dir = tmp_path / "batches"
    batches_dir.mkdir()
    course_file = batches_dir / "course.tsv"
    course_file.write_text("batch\tlevel\tnl\ten\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert resolve_batches_path("batches/course.tsv") == course_file
