"""Calculator tool — vulnerable eval() at level 0, safe parser at level 2+."""

import ast
import json
import operator

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node):
    """Recursively evaluate an AST node allowing only arithmetic."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op(_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op(_safe_eval(node.operand))
    raise ValueError(f"Unsupported expression element: {type(node).__name__}")


class CalculatorTool:
    def __init__(self, defense_manager=None):
        self.defense_manager = defense_manager

    def calculate(self, expression: str) -> str:
        """Evaluate a math expression."""
        level = self.defense_manager.level if self.defense_manager else 0

        if level >= 2:
            # Safe: AST-based math-only evaluator
            try:
                tree = ast.parse(expression, mode="eval")
                result = _safe_eval(tree)
                return json.dumps({"expression": expression, "result": result})
            except Exception as e:
                return json.dumps({"error": f"Invalid expression: {e}"})
        else:
            # Vulnerable: raw eval
            try:
                result = eval(expression)
                return json.dumps({"expression": expression, "result": str(result)})
            except Exception as e:
                return json.dumps({"error": f"Calculation error: {e}"})
