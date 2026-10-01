"""Unit tests for dungdra.geometry: does a line pass through a creature's square."""

from dungdra.geometry import segment_crosses_square


def test_a_line_through_the_middle_of_a_square_crosses_it():
    assert segment_crosses_square((2.5, 2.5), (32.5, 2.5), (15, 0), 5)


def test_a_diagonal_line_crosses_a_square_on_its_path():
    assert segment_crosses_square((0, 0), (30, 30), (12, 12), 5)


def test_a_square_off_the_line_is_not_crossed():
    assert not segment_crosses_square((2.5, 2.5), (32.5, 2.5), (15, 30), 5)


def test_a_square_beyond_the_end_is_not_crossed():
    assert not segment_crosses_square((2.5, 2.5), (32.5, 2.5), (45, 0), 5)


def test_grazing_an_edge_does_not_count():
    assert not segment_crosses_square((0, 5), (30, 5), (15, 0), 5)
    assert not segment_crosses_square((0, 0), (10, 10), (5, 0), 5)  # touches only a corner
