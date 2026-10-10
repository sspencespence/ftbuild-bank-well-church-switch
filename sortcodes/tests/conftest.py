import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

FIXTURES = HERE / "fixtures"
FIX_SORT_CODES = FIXTURES / "sort_codes.csv"
FIX_INSTITUTIONS = FIXTURES / "institutions.csv"


@pytest.fixture
def t():
    from sortcode_lookup import load_table
    return load_table(FIX_SORT_CODES, FIX_INSTITUTIONS)
