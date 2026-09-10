"""
Standard examples demonstrating AutoFix Agent's test-driven repair:
1. Runtime bug (ZeroDivisionError / NameError)
2. Logic bug with no runtime exception (silent incorrect calculation)
3. Correct code (runs clean, tests pass immediately)
4. Unfixable code (infinite loop or persistent syntax/logic violation)
"""

# ---------------------------------------------------------------------------
# 1. Runtime Bug Example (NameError / crash)
# ---------------------------------------------------------------------------

RUNTIME_BUG_CODE = """
def calculate_discount(price, discount_rate):
    # Bug: undefined variable 'rate_percent'
    return price * (1 - rate_percent)

calculate_discount(100, 0.2)
"""

RUNTIME_BUG_TEST = """
from solution import calculate_discount

def test_discount():
    assert calculate_discount(100, 0.2) == 80.0
"""

RUNTIME_BUG_FIXED = """
def calculate_discount(price, discount_rate):
    return price * (1 - discount_rate)

calculate_discount(100, 0.2)
"""


# ---------------------------------------------------------------------------
# 2. Logic Bug Example (Runs fine, exit 0, but wrong answer)
# ---------------------------------------------------------------------------

LOGIC_BUG_CODE = """
def is_even(n):
    # Runs without crashing, but logic is inverted!
    return n % 2 != 0
"""

LOGIC_BUG_TEST = """
from solution import is_even

def test_is_even():
    assert is_even(4) is True
    assert is_even(5) is False
"""

LOGIC_BUG_FIXED = """
def is_even(n):
    return n % 2 == 0
"""

# ---------------------------------------------------------------------------
# 3. Correct Code Example
# ---------------------------------------------------------------------------

CORRECT_CODE = """
def multiply(a, b):
    return a * b
"""

CORRECT_CODE_TEST = """
from solution import multiply

def test_multiply():
    assert multiply(3, 4) == 12
    assert multiply(-2, 5) == -10
"""

# ---------------------------------------------------------------------------
# 4. Unfixable Code Example (Infinite timeout loop)
# ---------------------------------------------------------------------------

UNFIXABLE_CODE = """
def spin():
    while True:
        pass

spin()
"""

UNFIXABLE_CODE_TEST = """
from solution import spin

def test_spin():
    assert spin() is None
"""
