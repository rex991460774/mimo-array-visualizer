from __future__ import annotations

from virtual_array.user_manual import (
    ManualChapter,
    ManualSection,
    manual_chapter_html,
    manual_chapter_search_text,
    manual_chapters,
)


EXPECTED_CHAPTER_KEYS = (
    "quick_start",
    "workspace",
    "layout_editing",
    "virtual_overview",
    "global_controls",
    "dbf_1d",
    "dbf_2d",
    "dbf_dictionary",
    "channel_patterns",
    "files_reports",
    "shortcuts_state",
    "troubleshooting",
)


def test_manual_has_matching_detailed_chapters_in_all_languages() -> None:
    for language in ("zh", "en", "ja"):
        chapters = manual_chapters(language)
        assert tuple(chapter.key for chapter in chapters) == EXPECTED_CHAPTER_KEYS
        assert len({chapter.key for chapter in chapters}) == len(chapters)
        for chapter in chapters:
            assert chapter.title.strip()
            assert chapter.summary.strip()
            assert len(chapter.sections) >= 2
            search_text = manual_chapter_search_text(chapter)
            assert len(search_text) >= 400, (language, chapter.key)
            rendered = manual_chapter_html(chapter).lower()
            assert "<h1" in rendered
            assert "<h2" in rendered
            assert "<ol" in rendered or "<ul" in rendered


def test_manual_covers_operational_workflows_and_recovery_details() -> None:
    chinese = "\n".join(
        manual_chapter_search_text(chapter) for chapter in manual_chapters("zh")
    )
    for required in (
        "1T1R",
        "0.5λ",
        "1～16",
        "50",
        "Ctrl+Shift+Z",
        "CSV/XLSX",
        "应用字典",
        "state.json",
        "不会恢复",
        "立即生效",
    ):
        assert required in chinese


def test_manual_renderer_escapes_all_content_fields() -> None:
    chapter = ManualChapter(
        key="escape_check",
        title="<title>",
        summary="<summary>",
        sections=(
            ManualSection(
                heading="<heading>",
                paragraphs=("<paragraph>",),
                steps=("<step>",),
                bullets=("<bullet>",),
                note="<note>",
                warning="<warning>",
            ),
        ),
    )
    rendered = manual_chapter_html(chapter)
    for raw in (
        "<title>",
        "<summary>",
        "<heading>",
        "<paragraph>",
        "<step>",
        "<bullet>",
        "<note>",
        "<warning>",
    ):
        assert raw not in rendered
    assert "&lt;title&gt;" in rendered
