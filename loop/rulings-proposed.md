# Proposed rulings

Rulings the test designer needs but the register doesn't have yet. Each one is waiting for review.

| Unit | Ambiguity | Proposed ruling | Tests |
|---|---|---|---|
| GLOSS.grappled | "unless you are Tiny or two or more sizes smaller than it": does a Tiny creature dragged by a Tiny grappler cost extra movement? | Read it literally: a Tiny grappled creature never adds extra movement cost, whatever the grappler's size. | `tests/srd/test_glossary.py::test_tiny_dragging_tiny_costs_nothing_extra` |
| GLOSS.grappled | "any target other than the grappler" when two creatures grapple you. | Attacks against any of your current grapplers have no Disadvantage from Grappled. Attacks against anyone else have it. | `tests/srd/test_glossary.py::test_two_grapplers_neither_attack_has_disadvantage` |
| GLOSS.grappled | "Your Speed is 0 and can't increase": does it cover special speeds, and speeds gained later? | Every speed (Climb, Swim, Fly, including speeds gained after the grapple starts) is 0 and can't increase while Grappled. | `tests/srd/test_glossary.py::test_grappled_special_speed_is_zero_too`, `::test_grappled_speed_cant_increase_with_a_bonus` |

- **GLOSS.grappled**: "unless you are Tiny or two or more sizes smaller than it": does a Tiny creature dragged by a Tiny grappler cost extra movement? — proposed: Read it literally: a Tiny grappled creature never adds extra movement cost, whatever the grappler's size.

- **GLOSS.grappled**: "any target other than the grappler" when two creatures grapple you. — proposed: Attacks against any of your current grapplers have no Disadvantage from Grappled. Attacks against anyone else have it.

- **GLOSS.grappled**: "Your Speed is 0 and can't increase": does it cover special speeds, and speeds gained later? — proposed: Every speed (Climb, Swim, Fly, including speeds gained after the grapple starts) is 0 and can't increase while Grappled.
