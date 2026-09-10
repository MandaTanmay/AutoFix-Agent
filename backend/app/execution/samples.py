"""
Sample programs for demonstrating AutoFix Agent's execution layer:
- Successful Python execution
- Python NameError
- JavaScript error
- Java compilation error
"""

PYTHON_SUCCESS = """
def add(a, b):
    return a + b

print(f"Result: {add(10, 20)}")
"""

PYTHON_NAME_ERROR = """
def greet(name):
    # Intentional bug: 'formatted_name' is not defined
    return f"Hello, {formatted_name}"

print(greet("World"))
"""

JAVASCRIPT_ERROR = """
function calculateTotal(items) {
    // Intentional bug: undefined variable access
    return items.reduce((acc, curr) => acc + curr.price, 0) + taxRate;
}

calculateTotal([{ price: 10 }]);
"""

JAVA_COMPILATION_ERROR = """
public class Calculator {
    public static void main(String[] args) {
        // Intentional syntax/type error: missing semicolon and incompatible types
        int number = "not_an_int"
        System.out.println(number);
    }
}
"""
