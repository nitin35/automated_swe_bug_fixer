import pytest
from calculator import add, divide

def test_add():
    assert add(2, 3) == 5

def test_divide():
    with pytest.raises(ValueError):
        divide(5, 0)
