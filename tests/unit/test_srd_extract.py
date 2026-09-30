"""Unit tests for the SRD extractor's layout and text logic (synthetic words; no PDF needed)."""

from scripts.srd import extract as X

BODY = "CFGFPT+Cambria"
BOLD = "CFGFPT+Cambria-BoldItalic"
HEAD = "CFGFPT+GillSans-SemiBold"
CELL = "JJYVJF+GillSans"


def w(text, x0, top, font=BODY, size=10.0, width=None):
    x1 = x0 + (width if width is not None else 5 * len(text))
    return X.Word(text, x0, x1, top, top + 10, font, size)


def line(*words, page=1):
    return X.Line(list(words), page)


def words_line(text, x0, top, font=BODY, size=10.0, page=1):
    """A line of words laid out left to right with normal word spacing."""
    out, x = [], x0
    for t in text.split():
        out.append(w(t, x, top, font, size))
        x += 5 * len(t) + 3
    return X.Line(out, page)


# ---------------------------------------------------------------- ids and references
def test_slug_drops_apostrophes_and_punctuation():
    assert X.slug("Arcanist’s Magic Aura") == "arcanists-magic-aura"
    assert X.slug("Level 1: Fighting Style") == "level-1-fighting-style"


def test_unit_id_skips_grouping_headings_tags_and_repeats():
    assert X.unit_id("GLOSS", ["Rules Definitions", "Grappled [Condition]"]) == "GLOSS.grappled"
    assert X.unit_id("CLASS", ["Fighter", "Fighter Class Features", "Level 2: Action Surge"]) == (
        "CLASS.fighter.level-2-action-surge"
    )
    assert X.unit_id("MONSTER", ["Assassin", "Assassin"]) == "MONSTER.assassin"
    assert X.unit_id("PLAY", []) == "PLAY"


def test_see_also_chapter_sections_and_glossary_entries():
    text = "An ability check is a D20 Test. See also “Playing the Game” (“D20 Tests” and “Proficiency”)."
    assert X.see_also(text) == ["Playing the Game › D20 Tests", "Playing the Game › Proficiency"]
    assert X.see_also("An adventure. See also “Encounter.”") == ["Encounter"]
    assert X.see_also("See also “Cover.” If the creator of an area of effect places it") == ["Cover"]
    assert X.see_also("No references here.") == []


def test_dedupe_numbers_repeated_ids_in_document_order():
    units = X._dedupe([{"id": "A"}, {"id": "A"}, {"id": "B"}, {"id": "A"}])
    assert [u["id"] for u in units] == ["A", "A-2", "B", "A-3"]


# ---------------------------------------------------------------- lines
def test_line_text_spacing_follows_gaps_including_wrapped_lines():
    assert line(w("Grappled", 10, 0, width=40), w(".", 50.5, 0, width=2)).text == "Grappled."
    assert line(w("Two", 10, 0, width=15), w("words", 30, 0)).text == "Two words"
    # a merged heading: the second word starts left of the first word's end (next line)
    assert line(w("Draconic", 200, 0, HEAD, 12, width=50), w("Sorcery", 63, 14, HEAD, 12)).text == (
        "Draconic Sorcery"
    )


def test_heading_detection_by_font_and_size():
    assert words_line("Grappled", 63, 0, HEAD, 12.0).heading_size == 12
    assert words_line("Combat", 63, 0, HEAD, 13.999999).heading_size == 14
    assert words_line("Cover", 63, 0, HEAD, 10.5).heading_size is None  # table title
    assert words_line("Grappled", 63, 0, BODY, 12.0).heading_size is None


def test_merge_wrapped_headings_same_size_close_or_unclosed_paren():
    a = words_line("Spell Scroll (Cantrip, 30 GP;", 63, 700, HEAD, 12.0)
    b = words_line("Level 1, 50 GP)", 313, 40, HEAD, 12.0)  # continues at the top of the next column
    merged = X.merge_wrapped_headings([a, b])
    assert len(merged) == 1 and merged[0].text.endswith("GP; Level 1, 50 GP)")
    c = words_line("Grappled", 63, 100, HEAD, 12.0)
    d = words_line("Prone", 63, 300, HEAD, 12.0)
    assert len(X.merge_wrapped_headings([c, d])) == 2


# ---------------------------------------------------------------- characters to words
class FakePage:
    height = 783.0

    def __init__(self, chars):
        self.chars = chars


def ch(text, x0, x1, font="X+Cambria", size=10.0, base=500.0):
    return {
        "text": text,
        "x0": x0,
        "x1": x1,
        "fontname": font,
        "size": size,
        "matrix": (1, 0, 0, 1, x0, base),
    }


def chars_for(text, x0=63.0, font="X+Cambria", size=10.0, width=5.0):
    out, x = [], x0
    for c in text:
        out.append(ch(c, x, x + (2.2 if c == " " else width), font, size))
        x += 2.2 if c == " " else width
    return out


def test_page_words_space_without_visual_gap_is_not_a_word_break():
    chars = chars_for("Short")
    last = chars[-1]["x1"]
    chars += [ch(" ", last, last + 2.6), *chars_for("sword", x0=last)]  # the "s" starts where the space does
    assert [w.text for w in X.page_words(FakePage(chars))] == ["Shortsword"]
    assert [w.text for w in X.page_words(FakePage(chars_for("two words")))] == ["two", "words"]


def test_page_words_small_caps_case_comes_from_glyph_size_and_fractions_are_unicode():
    sc = "X+GillSans-SemiBold-SC700"
    sizes = [
        12,
        8.4,
        8.4,
        8.4,
        12,
        12,
        8.4,
        8.4,
        8.4,
        8.4,
        8.4,
    ]  # "Acid SplASh": the case in the text layer lies
    chars, x = [], 63.0
    for c, sz in zip("Acid SplASh", sizes, strict=True):
        chars.append(ch(c, x, x + (2.2 if c == " " else 5), sc, sz))
        x += 2.2 if c == " " else 5.0
    assert [w.text for w in X.page_words(FakePage(chars))] == ["Acid", "Splash"]
    frac = chars_for("up to 1")
    frac.append(ch("1/2", frac[-1]["x1"], frac[-1]["x1"] + 5))
    assert [w.text for w in X.page_words(FakePage(frac))][-1] == "1½"


# ---------------------------------------------------------------- page layout
def test_reading_order_left_column_before_right_and_wide_rows_split_bands():
    words = [
        w("R1", 313, 50),
        w("L1", 63, 50),
        w("L2", 63, 62),
        w("R2", 313, 62),
        w("WIDE", 250, 100, width=100),  # crosses the gutter at x=297
        w("L3", 63, 140),
        w("R3", 313, 140),
        w("footer", 63, 747),
    ]
    assert [ln.text for ln in X.reading_order(words, 1)] == ["L1", "L2", "R1", "R2", "WIDE", "L3", "R3"]


def test_crosses_gutter_when_text_runs_across_the_midline():
    assert X._crosses_gutter([w("feet", 281, 0, width=15), w("in", 299, 0, width=7)])
    assert X._crosses_gutter([w("Handling", 250, 0, width=100)])  # straddles the gutter
    assert not X._crosses_gutter([w("left", 250, 0, width=37), w("right", 313, 0)])  # a real column gap


def test_render_table_row_running_across_the_gutter_is_not_cut():
    lines = [
        X.Line([w("Skill", 67, 0, HEAD, 9.25, width=18), w("Example", 229, 0, HEAD, 9.25, width=36)], 1),
        X.Line(
            [w("Acrobatics", 67, 15, CELL, 9.5, width=42), w("feet", 281, 15, CELL, 9.5, width=15)]
            + [w("in", 299, 15, CELL, 9.5, width=7), w("stunt.", 309, 15, CELL, 9.5, width=24)],
            1,
        ),
    ]
    assert X.render_table(lines).splitlines()[2] == "| Acrobatics | feet in stunt. |"


def test_structure_flags_a_table_cut_down_the_middle():
    text = "| Skill | Uses |\n| --- | --- |\n| A | x |\n| B | y |\n| x2 |  |\n| y2 |  |\n| z2 |  |"
    assert X.structure([{"id": "S", "chapter": "C", "pages": [9, 9], "text": text}]) == [
        "S: 3 of 5 table rows have text only in the first cell"
    ]


# ---------------------------------------------------------------- text assembly
def test_join_lines_hyphen_kept_only_for_known_compounds():
    a, b = words_line("a three-", 63, 0), words_line("quarters cover and pro-", 63, 12)
    c = words_line("vide cover", 63, 24)
    assert X.join_lines([a, b, c], {"three-quarters"}) == "a three-quarters cover and provide cover"


def test_join_lines_run_in_labels_and_gaps_start_paragraphs():
    intro = words_line("While you have the Grappled condition, you experience the following effects.", 63, 0)
    label = X.Line(
        [w("Speed", 63, 12, BOLD, width=25), w("0.", 91, 12, BOLD)]
        + words_line("Your Speed is 0.", 105, 12).words,
        1,
    )
    para = words_line("Another paragraph.", 63, 40)
    assert X.join_lines([intro, label, para], set()) == (
        "While you have the Grappled condition, you experience the following effects.\n\n"
        "Speed 0. Your Speed is 0.\n\nAnother paragraph."
    )


def test_join_lines_marks_inner_headings_and_sidebar_titles():
    body = words_line("Text.", 63, 0)
    inner = words_line("Combat Step by Step", 63, 20, HEAD, 12.0)
    sidebar = words_line("Selling Equipment", 63, 50, "X+GillSans-Bold-SC700", 11.0)
    out = X.join_lines([body, inner, sidebar], set())
    assert out == "Text.\n\n#### Combat Step by Step\n\nSelling Equipment"


def test_join_lines_numbered_steps_and_bullets_are_paragraphs_and_wrapped_labels_join():
    step1 = X.Line(
        [w("1:", 63, 0, BOLD, width=8), w("Describe", 75, 0, BOLD)] + words_line("a scene.", 120, 0).words, 1
    )
    step2 = X.Line([w("2:", 63, 12, BOLD, width=8), w("The", 75, 12, BOLD), w("Players", 95, 12, BOLD)], 1)
    step2b = X.Line([w("Do.", 63, 24, BOLD, width=15)] + words_line("They act.", 81, 24).words, 1)
    bullet1, bullet2 = words_line("• Gain the traits.", 63, 36), words_line("• Gain the features.", 63, 48)
    assert X.join_lines([step1, step2, step2b, bullet1, bullet2], set()) == (
        "1: Describe a scene.\n\n2: The Players Do. They act.\n\n• Gain the traits.\n\n• Gain the features."
    )


def test_join_lines_prose_flows_across_a_column_break_and_sidebars_move_last():
    a = words_line("This holds whether the", 63, 690)
    title = words_line("EXCEPTIONS", 63, 700, "X+GillSans-Bold-SC700", 11.0)
    box = words_line("General rules govern.", 63, 712, CELL, 9.0)
    b = words_line("adventurers are talking.", 313, 40)  # top of the next column, mid-sentence
    assert X.join_lines([a, title, box, b], set()) == (
        "This holds whether the adventurers are talking.\n\nEXCEPTIONS\n\nGeneral rules govern."
    )


def test_join_lines_minor_heading_and_formula_continuation():
    minor = words_line("Write Your Level", 63, 0, HEAD, 10.5)
    body = words_line("Write your level.", 63, 14)
    f1 = words_line("Melee attack bonus = Strength modifier", 63, 40, HEAD, 10.0)
    f2 = words_line("+ Proficiency Bonus", 63, 52, HEAD, 10.0)
    assert X.join_lines([minor, body, f1, f2], set()) == (
        "#### Write Your Level\n\nWrite your level.\n\n"
        "Melee attack bonus = Strength modifier + Proficiency Bonus"
    )


def test_merge_wrapped_headings_lowercase_continuation_across_columns():
    a = words_line("Amulet of Proof against Detection", 63, 700, HEAD, 12.0)
    b = words_line("and Location", 313, 40, HEAD, 12.0)
    assert [h.text for h in X.merge_wrapped_headings([a, b])] == [
        "Amulet of Proof against Detection and Location"
    ]


def test_join_lines_table_in_the_middle_of_a_sentence_waits_for_the_sentence_to_end():
    a = words_line("Replace it with another one for which you", 63, 600)
    table = [words_line("Warlock Features", 63, 620, HEAD, 10.5)]
    table += [X.Line([w("Level", 67, 636, HEAD, 9.25)], 1), X.Line([w("1", 67, 650, CELL, 9.5)], 1)]
    b = words_line("qualify. You can’t replace it.", 313, 40)
    assert X.join_lines([a, *table, b], set()) == (
        "Replace it with another one for which you qualify. You can’t replace it.\n\n"
        "Table: Warlock Features\n| Level |\n| --- |\n| 1 |"
    )


# ---------------------------------------------------------------- tables
def _cover_table(x_shift=0.0, with_title=True):
    s = x_shift
    lines = [words_line("Cover", 63 + s, 0, HEAD, 10.5)] if with_title else []
    lines += [
        X.Line([w("Degree", 67 + s, 16, HEAD, 9.25), w("Benefit", 111 + s, 16, HEAD, 9.25)], 1),
        X.Line(
            [
                w("Half", 67 + s, 30, CELL, 9.5),
                w("+2", 111 + s, 30, CELL, 9.5),
                w("bonus", 124 + s, 30, CELL, 9.5),
            ],
            1,
        ),
        X.Line([w("Three-", 67 + s, 43, CELL, 9.5), w("+5", 111 + s, 43, CELL, 9.5)], 1),
        X.Line([w("Quarters", 67 + s, 55, CELL, 9.5, width=35), w("bonus", 111 + s, 55, CELL, 9.5)], 1),
    ]
    return lines


def test_render_table_columns_from_header_and_wrapped_first_cells():
    assert X.render_table(_cover_table()) == (
        "Table: Cover\n| Degree | Benefit |\n| --- | --- |\n"
        "| Half | +2 bonus |\n| Three-Quarters | +5 bonus |"
    )


def test_render_table_right_aligned_numbers_use_midpoint_boundaries():
    lines = [
        words_line("Gear", 63, 0, HEAD, 10.5),
        X.Line([w("Item", 67, 16, HEAD, 9.25, width=20), w("Cost", 266, 16, HEAD, 9.25, width=20)], 1),
        X.Line(
            [
                w("Acid", 67, 30, CELL, 9.5),
                w("25", 250, 30, CELL, 9.5, width=10),
                w("GP", 262, 30, CELL, 9.5),
            ],
            1,
        ),
    ]
    assert X.render_table(lines).splitlines()[-1] == "| Acid | 25 GP |"


def test_render_table_flowing_into_next_column_keeps_both_parts():
    left = _cover_table()
    right = [ln for ln in _cover_table(x_shift=250, with_title=False)[1:]]  # body only, no header
    out = X.render_table(left + right)
    assert out.count("| Half | +2 bonus |") == 2 and out.count("| Degree | Benefit |") == 1


def test_render_table_cell_overflowing_its_header_stays_in_its_column():
    lines = [
        X.Line(
            [w("Level", 68, 0, HEAD, 9.25, width=22), w("Features", 155, 0, HEAD, 9.25, width=40)]
            + [w("Sneak", 450, 0, HEAD, 9.25, width=24)],
            1,
        ),
        X.Line(
            [w("1", 77, 15, CELL, 9.5, width=4), w("Thieves’", 155, 15, CELL, 9.5, width=32)]
            + [w("Mastery", 190, 15, CELL, 9.5, width=190), w("1d6", 472, 15, CELL, 9.5, width=14)],
            1,
        ),
        X.Line(
            [
                w("2", 77, 30, CELL, 9.5, width=4),
                w("Cunning", 155, 30, CELL, 9.5),
                w("1d6", 472, 30, CELL, 9.5),
            ],
            1,
        ),
    ]
    assert X.render_table(lines).splitlines()[2] == "| 1 | Thieves’ Mastery | 1d6 |"


def test_render_table_two_level_header_and_label_rows():
    lines = [
        X.Line([w("Pace", 67, 0, HEAD, 9.25, width=18), w("Distance", 140, 0, HEAD, 9.25, width=36)], 1),
        X.Line([w("Minute", 120, 12, HEAD, 9.25, width=28), w("Hour", 180, 12, HEAD, 9.25, width=20)], 1),
        X.Line([w("Martial", 67, 27, CELL, 9.5, width=30), w("Weapons", 100, 27, CELL, 9.5, width=85)], 1),
        X.Line(
            [
                w("Fast", 67, 42, CELL, 9.5, width=18),
                w("400", 120, 42, CELL, 9.5),
                w("4", 180, 42, CELL, 9.5),
            ],
            1,
        ),
    ]
    assert X.render_table(lines).splitlines() == [
        "| Pace | Distance Minute | Hour |",
        "| --- | --- | --- |",
        "| Martial Weapons |  |  |",
        "| Fast | 400 | 4 |",
    ]


def test_render_table_wrapped_first_cell_joins_its_row():
    lines = [
        X.Line([w("Example", 67, 0, HEAD, 9.25, width=30), w("DC", 250, 0, HEAD, 9.25, width=10)], 1),
        X.Line([w("A", 67, 14, CELL, 9.5), w("10", 250, 14, CELL, 9.5)], 1),
        X.Line([w("wraps", 67, 26, CELL, 9.5)], 1),  # 12pt below: a wrapped line
        X.Line([w("B", 67, 41, CELL, 9.5), w("15", 250, 41, CELL, 9.5)], 1),
    ]
    assert X.render_table(lines).splitlines()[2:] == ["| A wraps | 10 |", "| B | 15 |"]


def test_table_footnotes_end_the_table_and_each_starts_a_paragraph():
    lines = [
        words_line("Rare Languages", 313, 0, HEAD, 10.5),
        X.Line([w("Language", 317, 16, HEAD, 9.25, width=35)], 1),
        X.Line([w("Primordial*", 317, 30, CELL, 9.5, width=45)], 1),
        words_line("*Primordial includes the Aquan", 313, 50, CELL, 8.0),
        words_line("and Terran dialects.", 313, 59, CELL, 8.0),
        words_line("†Rate of travel varies.", 313, 68, CELL, 8.0),
    ]
    assert X.join_lines(lines, set()) == (
        "Table: Rare Languages\n| Language |\n| --- |\n| Primordial* |\n\n"
        "*Primordial includes the Aquan and Terran dialects.\n\n†Rate of travel varies."
    )


def test_render_table_repeated_column_groups_are_stacked():
    lines = [
        X.Line([w("Task", 67, 0, HEAD, 9.25, width=20), w("DC", 150, 0, HEAD, 9.25, width=10)], 1),
        X.Line([w("Task", 317, 0, HEAD, 9.25, width=20), w("DC", 400, 0, HEAD, 9.25, width=10)], 1),
        X.Line([w("Easy", 67, 14, CELL, 9.5), w("10", 150, 14, CELL, 9.5)], 1),
        X.Line([w("Hard", 317, 14, CELL, 9.5), w("20", 400, 14, CELL, 9.5)], 1),
        X.Line([w("Medium", 67, 28, CELL, 9.5), w("15", 150, 28, CELL, 9.5)], 1),
    ]
    assert X.render_table(lines).splitlines() == [
        "| Task | DC |",
        "| --- | --- |",
        "| Easy | 10 |",
        "| Medium | 15 |",
        "| Hard | 20 |",
    ]


def test_reading_order_table_header_across_the_gutter_keeps_the_table_together():
    words = [
        w("Level", 68, 400, HEAD, 9.25, width=22),
        w("Cantrips", 320, 400, HEAD, 9.25, width=35),
        w("1", 77, 415, CELL, 9.5, width=4),
        w("3", 330, 415, CELL, 9.5, width=4),
        w("Prose", 313, 100),  # right-column text above the table
    ]
    assert [ln.text for ln in X.reading_order(words, 1)] == ["Prose", "Level Cantrips", "1 3"]


def test_header_partly_regular_face_counts_only_when_body_starts_regular():
    header = [w("Terrain", 67, 0, HEAD, 9.25), w("Distance", 229, 0, CELL, 9.5)]  # half the header is regular
    body = [w("Arctic", 67, 15, CELL, 9.5), w("20", 229, 15, CELL, 9.5)]
    assert X._header_count([header, body]) == 1
    label_row = [w("Primary", 67, 0, HEAD, 9.5), w("Strength", 150, 0, CELL, 9.5)]
    next_label = [w("Hit", 67, 15, HEAD, 9.5), w("D12", 150, 15, CELL, 9.5)]
    assert X._header_count([label_row, next_label]) == 0


def test_label_value_table_joins_wrapped_labels_and_values():
    lines = [
        words_line("Core Traits", 63, 0, HEAD, 10.5),
        X.Line(
            [
                w("Saving", 67, 16, HEAD, 9.5, width=28),
                w("Throw", 98, 16, HEAD, 9.5),
                w("Str", 150, 16, CELL, 9.5),
            ],
            1,
        ),
        X.Line([w("Proficiencies", 67, 28, HEAD, 9.5, width=55)], 1),
        X.Line(
            [w("Skill", 67, 43, HEAD, 9.5), w("Animal", 150, 43, CELL, 9.5), w("Na-", 185, 43, CELL, 9.5)], 1
        ),
        X.Line([w("ture", 150, 55, CELL, 9.5)], 1),
    ]
    assert X.render_table(lines).splitlines() == [
        "Table: Core Traits",
        "| | |",
        "| --- | --- |",
        "| Saving Throw Proficiencies | Str |",
        "| Skill | Animal Nature |",
    ]


def test_join_cell_hyphen_rules():
    assert X._join_cell("Na-", "ture", set()) == "Nature"
    assert X._join_cell("Three-", "Quarters", set()) == "Three-Quarters"
    assert X._join_cell("two-", "handed", {"two-handed"}) == "two-handed"
    assert X._join_cell("a", "b", set()) == "a b" and X._join_cell("", "b", set()) == "b"


def test_render_table_rows_never_mix_pages():
    p26 = [X.Line([w("1d100", 317, 40, HEAD, 9.25, width=25), w("Trinket", 370, 40, HEAD, 9.25)], 26)]
    p26 += [X.Line([w("01", 317, 55, CELL, 9.5, width=10), w("A hand", 370, 55, CELL, 9.5)], 26)]
    p27 = [X.Line([w("1d100", 67, 40, HEAD, 9.25, width=25), w("Trinket", 120, 40, HEAD, 9.25)], 27)]
    p27 += [X.Line([w("02", 67, 55, CELL, 9.5, width=10), w("A glove", 120, 55, CELL, 9.5)], 27)]
    lines = [words_line("Trinkets", 313, 20, HEAD, 10.5, page=26), *p26, *p27]
    assert X.render_table(lines).splitlines() == [
        "Table: Trinkets",
        "| 1d100 | Trinket |",
        "| --- | --- |",
        "| 01 | A hand |",
        "| 02 | A glove |",
    ]


def test_die_gaps():
    assert X._die_gaps(["01", "02–99", "00"], 100) is None
    assert X._die_gaps(["1", "3"], 4) == "expected 2, found '3'"
    assert X._die_gaps(["1", "2"], 4) == "ends at 2, not 4"


def test_relocate_tables_moves_table_to_the_unit_that_names_it():
    table = "Table: Weapons\n| Name |\n| --- |\n| Club |"
    units = [
        {
            "id": "W",
            "chapter": "Equipment",
            "title": "Weapons",
            "pages": [89, 89],
            "text": "The Weapons table lists.",
        },
        {
            "id": "V",
            "chapter": "Equipment",
            "title": "Vex",
            "pages": [91, 91],
            "text": f"Advantage.\n\n{table}",
        },
    ]
    X.relocate_tables(units)
    assert units[1]["text"] == "Advantage."
    assert units[0]["text"].endswith(table) and units[0]["pages"] == [89, 91]


def test_spell_lists_agree_with_spell_descriptions():
    def spell(title, line):
        return {
            "id": f"SPELL.{title}",
            "chapter": "Spells",
            "heading_path": ["Spell Descriptions", title],
            "title": title,
            "pages": [1, 1],
            "text": f"{line}\nCasting Time: Action",
        }

    lists = {
        "id": "CLASS.druid.spell-list",
        "chapter": "Classes",
        "heading_path": [],
        "title": "",
        "pages": [1, 1],
        "text": "Table: Level 4 Druid Spells\n| Spell | School | Special |\n| --- | --- | --- |\n"
        "| Ice Storm | Evocation | — |\n| Heal | Abjuration | — |",
    }
    units = [
        lists,
        spell("Ice Storm", "Level 4 Evocation (Druid, Sorcerer, Wizard)"),
        spell("Heal", "Level 6 Abjuration (Cleric, Druid)"),
        spell("Mind Spike", "Level 2 Divination (Sorcerer, Warlock)"),
    ]
    assert X.spell_lists(units) == [
        "CLASS.druid.spell-list: 'Heal' listed as Druid level 4, "
        "described as 'Level 6 Abjuration (Cleric, Druid)'",
        "SPELL.Ice Storm: Sorcerer spell 'Ice Storm' is missing from the Sorcerer spell list",
        "SPELL.Ice Storm: Wizard spell 'Ice Storm' is missing from the Wizard spell list",
        "SPELL.Heal: Cleric spell 'Heal' is missing from the Cleric spell list",
        "SPELL.Mind Spike: Warlock spell 'Mind Spike' is missing from the Warlock spell list",
    ]  # Sorcerer / Mind Spike is a known SRD omission


def test_structure_flags_stray_numbers_and_broken_level_columns():
    good = "| Level | PB |\n| --- | --- |\n" + "".join(f"| {i} | +2 |\n" for i in range(1, 21))
    short = "| Level | PB |\n| --- | --- |\n" + "".join(f"| {i} | +2 |\n" for i in range(1, 20))
    units = [
        {"id": "A", "chapter": "C", "pages": [1, 1], "text": good},
        {"id": "B", "chapter": "C", "pages": [2, 2], "text": short + "\n20\n\n+6"},
    ]
    problems = X.structure(units)
    assert problems == [
        "B: stray number '20' outside a table",
        "B: stray number '+6' outside a table",
        f"B: Level column is not 1..20 in order: {list(range(1, 20))}",
    ]


def test_relocate_tables_handles_consecutive_tables():
    t1, t2 = "Table: Alpha\n| A |\n| --- |\n| 1 |", "Table: Beta\n| B |\n| --- |\n| 2 |"
    units = [
        {"id": "A", "chapter": "M", "title": "A", "pages": [1, 1], "text": "See the Alpha table."},
        {"id": "B", "chapter": "M", "title": "B", "pages": [1, 1], "text": "See the Beta table."},
        {"id": "C", "chapter": "M", "title": "C", "pages": [2, 2], "text": f"Other text.\n\n{t1}\n\n{t2}"},
    ]
    X.relocate_tables(units)
    assert (
        units[0]["text"].endswith(t1) and units[1]["text"].endswith(t2) and units[2]["text"] == "Other text."
    )


# ---------------------------------------------------------------- fix-ups
def test_fixups_turn_ability_grids_into_tables_and_keep_odd_values_verbatim():
    grid = (
        "MOD SAVE\n\nMOD SAVE\n\nMOD SAVE\n\n"
        "Str 8 −1 −1 Dex 15 +2 +2 Con22 +6 +12\n\nInt 6 −2 2 WIS 8 −1 −1 Cha 8 −1 −1"
    )
    unit = {"text": f"Speed 30 ft.\n\n{grid}\n\nSkills Stealth +6"}
    X.fixups([unit])
    assert unit["text"] == (
        "Speed 30 ft.\n\n| Ability | Score | Mod | Save |\n| --- | --- | --- | --- |\n"
        "| Str | 8 | −1 | −1 |\n| Dex | 15 | +2 | +2 |\n| Con | 22 | +6 | +12 |\n"
        "| Int | 6 | −2 | 2 |\n| Wis | 8 | −1 | −1 |\n| Cha | 8 | −1 | −1 |\n\nSkills Stealth +6"
    )


def test_fixups_leave_an_unrecognised_grid_alone():
    odd = "MOD SAVE\n\nMOD SAVE\n\nMOD SAVE\n\nStr 8 −1 −1\n\nsomething else"
    unit = {"text": odd}
    assert X.fixups([unit])[0]["text"] == odd


# ---------------------------------------------------------------- gate
def _unit(i, pages, text="x", chapter="Playing the Game", path=("A",)):
    return {
        "id": i,
        "chapter": chapter,
        "heading_path": list(path),
        "title": path[-1],
        "pages": pages,
        "text": text,
    }


def test_check_reports_duplicates_empty_text_and_uncovered_pages():
    units = [_unit("A", [5, 200]), _unit("A", [201, 364], text=" ")]
    units += [
        _unit(f"G{i}", [300, 300], chapter="Rules Glossary", path=("Rules Definitions", f"E{i}"))
        for i in range(155)
    ]
    assert X.check(units) == ["duplicate id A", "A: empty text"]
    gap = [_unit("B", [5, 100])] + units[2:]
    assert any("pages without any unit" in p for p in X.check(gap))


def test_check_with_pdf_lines_flags_lost_prose_and_characters():
    units = [
        _unit(f"G{i}", [5, 364], chapter="Rules Glossary", path=("Rules Definitions", f"E{i}"))
        for i in range(155)
    ]
    kept = words_line("This sentence made it into a unit intact.", 63, 0)
    lost = words_line("This sentence was dropped by the extractor somehow.", 63, 20)
    units[0]["text"] = kept.text
    problems = X.check(units, {"Rules Glossary": [kept, lost]})
    assert len(problems) == 2
    assert problems[0].startswith("1 prose lines missing") and "PDF characters missing" in problems[1]
    assert X.check(units, {"Rules Glossary": [kept]}) == []
