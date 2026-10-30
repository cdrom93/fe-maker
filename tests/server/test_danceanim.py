import pytest

from fe_maker.decomp import danceanim

SOURCE = f"""#include "global.h"

void sub_80812C0(void)
{{
{danceanim._START}}}

void sub_80813C0(void)
{{
{danceanim._STOP}}}
"""


def test_both_animation_changes_are_guarded():
    out = danceanim.with_guard(SOURCE)
    assert out.count("if (FemHasDanceAnim())") == 2
    assert out.index("static int FemHasDanceAnim") < out.index("void sub_80812C0")


def test_another_decomp_is_refused():
    with pytest.raises(danceanim.DanceAnimError):
        danceanim.with_guard("void other(void) {}")
