"""Unit tests for dungdra.geometry: does a line pass through a creature's square, and is a point
inside an area."""

import pytest

from dungdra.geometry import (
    dist_points,
    in_area,
    in_cone_direction,
    in_cube_at_point,
    in_cube_direction,
    segment_crosses_square,
    squares_overlap,
    steps_between,
)


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


def test_a_cone_narrows_upward_as_it_does_sideways():
    assert in_cone_direction((0, 0, 0), (5, 0, 0), (10, 0, 5))
    assert not in_cone_direction((0, 0, 0), (5, 0, 0), (10, 0, 10))


def test_a_cone_aimed_up_at_a_flyer_follows_it():
    assert in_cone_direction((0, 0, 0), (5, 0, 10), (5, 0, 10))
    assert not in_cone_direction((0, 0, 0), (5, 0, 10), (10, 0, 0))


def test_a_cube_extends_its_side_from_the_origin_and_half_of_it_to_each_side():
    assert in_cube_direction((0, 0), (5, 0), (15, 0), 15)
    assert in_cube_direction((0, 0), (5, 0), (5, 5), 15)
    assert not in_cube_direction((0, 0), (5, 0), (20, 0), 15)
    assert not in_cube_direction((0, 0), (5, 0), (5, 10), 15)


def test_a_cube_doesnt_contain_its_origin_or_anything_behind_it():
    assert not in_cube_direction((0, 0), (5, 0), (0, 0), 15)
    assert not in_cube_direction((0, 0), (5, 0), (-5, 0), 15)
    assert not in_cube_direction((0, 0), (0, 0), (5, 0), 15)


def test_a_cube_reaches_half_its_side_above_and_below_its_origin():
    assert in_cube_direction((0, 0, 0), (5, 0, 0), (5, 0, 5), 15)
    assert not in_cube_direction((0, 0, 0), (5, 0, 0), (5, 0, 10), 15)
    assert not in_cube_direction((0, 0, 20), (5, 0, 20), (5, 0, 0), 15)


def test_a_point_without_an_elevation_is_on_the_ground():
    assert dist_points((0, 0), (5, 0, 20)) == 20
    assert dist_points((0, 0), (10, 5)) == 10


def test_in_area_measures_each_shape_from_its_origin():
    assert in_area("sphere", 5, (40, 0), (45, 5))
    assert not in_area("sphere", 5, (40, 0), (40, 0, 10))
    assert in_area("cone", 15, (0, 0), (15, 0), toward=(5, 0))
    assert not in_area("cone", 15, (0, 0), (20, 0), toward=(5, 0))
    assert in_area("Cube", 15, (0, 0), (15, 5), toward=(5, 0))
    assert not in_area("cube", 15, (0, 0), (-5, 0), toward=(5, 0))


def test_an_even_cube_at_a_point_centres_on_the_squares_top_right_corner():
    # 20 ft at (15, 10): columns 10-25, rows 5-20 (R-35)
    inside = [
        (x, y) for x in range(-10, 50, 5) for y in range(-15, 45, 5) if in_cube_at_point((15, 10), (x, y), 20)
    ]
    assert sorted({x for x, _ in inside}) == [10, 15, 20, 25]
    assert sorted({y for _, y in inside}) == [5, 10, 15, 20]
    assert len(inside) == 16


def test_an_odd_cube_at_a_point_centres_on_the_square():
    inside = [
        (x, y) for x in range(-10, 50, 5) for y in range(-15, 45, 5) if in_cube_at_point((15, 10), (x, y), 15)
    ]
    assert sorted(inside) == [(x, y) for x in (10, 15, 20) for y in (5, 10, 15)]


def test_naming_a_neighbouring_square_moves_the_cube_one_square_that_way():
    def squares(point):
        grid = [(x, y) for x in range(-10, 50, 5) for y in range(-15, 45, 5)]
        return {(x, y) for x, y in grid if in_cube_at_point(point, (x, y), 20)}

    assert squares((20, 10)) == {(x + 5, y) for x, y in squares((15, 10))}
    assert squares((15, 5)) == {(x, y - 5) for x, y in squares((15, 10))}


def test_a_cube_at_a_point_rests_on_the_ground_and_extends_upward():
    assert in_cube_at_point((15, 10), (15, 10, 20), 20)
    assert not in_cube_at_point((15, 10), (15, 10, 25), 20)
    assert not in_cube_at_point((15, 10, 10), (15, 10, 5), 20)


def test_in_area_places_a_cube_without_a_direction_at_its_origin():
    assert in_area("cube", 20, (30, 0), (30, 0))
    assert not in_area("cube", 20, (30, 0), (30, 100))


def test_in_area_refuses_a_shape_without_a_direction_or_geometry():
    with pytest.raises(ValueError, match="direction"):
        in_area("cone", 15, (0, 0), (5, 0))
    with pytest.raises(ValueError, match="geometry"):
        in_area("line", 30, (0, 0), (5, 0), toward=(5, 0))


def test_steps_between_lists_each_square_entered_but_not_the_start():
    assert steps_between((0, 0), (15, 0)) == [(5, 0), (10, 0), (15, 0)]
    assert steps_between((0, 0), (10, 5)) == [(5, 5), (10, 5)]
    assert steps_between((0, 0), (0, 0)) == []


def test_steps_between_ignores_elevation_and_never_overshoots_an_off_grid_end():
    assert steps_between((0, 0, 10), (10, 0, 10)) == [(5, 0), (10, 0)]
    assert steps_between((0, 0), (7, 0)) == [(5, 0)]


def test_squares_overlap_only_when_their_interiors_meet():
    assert squares_overlap((5, 0), 5, (0, 0), 10)
    assert squares_overlap((5, 0), 5, (5, 0), 5)
    assert not squares_overlap((5, 0), 5, (10, 0), 5)  # shares an edge
    assert not squares_overlap((5, 5), 5, (0, 0), 5)  # shares a corner
