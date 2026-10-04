"""Unit tests for dungdra.geometry: does a line pass through a creature's square."""

from dungdra.geometry import in_cone_direction, segment_crosses_square


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


def test_a_cone_contains_points_along_its_axis_but_not_behind_its_origin():
    assert in_cone_direction((0, 0), (5, 0), (10, 0))
    assert not in_cone_direction((0, 0), (5, 0), (-5, 0))
    assert not in_cone_direction((0, 0), (5, 0), (0, 0))


def test_a_cones_width_equals_the_distance_from_its_origin():
    assert in_cone_direction((0, 0), (5, 0), (10, 5))
    assert not in_cone_direction((0, 0), (5, 0), (10, 10))


def test_a_cone_with_no_direction_contains_nothing():
    assert not in_cone_direction((0, 0), (0, 0), (5, 0))
