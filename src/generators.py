# --- AST TO RAPCODE GENERATOR ---

def _generate_expression_string_rapcode(node):
    if node is None: return ""
    node_type = node.get("type")
    if node_type == "Literal":
        value = node.get("value")
        if isinstance(value, str): return f'"{value}"'
        if isinstance(value, bool): return "TRUE" if value else "FALSE"
        return str(value)
    if node_type == "Identifier": return node.get("name", "")
    if node_type == "BinaryExpression":
        left = _generate_expression_string_rapcode(node.get("left"))
        right = _generate_expression_string_rapcode(node.get("right"))
        operator = node.get("operator", "")
        return f"({left} {operator} {right})"
    if node_type == "CallExpression" and node.get("callee") == "Input":
        prompt_literal = node.get("prompt", '""')
        return f'INPUT({prompt_literal})'
    return ""

def generate_rapcode_from_ast(ast_nodes, indent_level=0):
    """
    Recursively traverses the AST and generates formatted .rapcode lines.
    (This is the corrected version).
    """
    code_lines = []
    indent = "  " * indent_level

    for node in ast_nodes:
        node_type = node.get("type")

        if node_type == "AssignmentStatement":
            left = _generate_expression_string_rapcode(node.get("left"))
            right = _generate_expression_string_rapcode(node.get("right"))
            code_lines.append(f'{indent}{left} := {right}')

        elif node_type == "ExpressionStatement":
            expression = node.get("expression", {})
            if expression.get("callee") == "Output":
                arg_node = expression.get("arguments", [])[0]
                arg_string = _generate_expression_string_rapcode(arg_node)
                code_lines.append(f'{indent}OUTPUT {arg_string}')

        elif node_type == "IfStatement":
            consequent = node.get("consequent", {}).get("body", [])
            alternate = node.get("alternate", {}).get("body", []) if node.get("alternate") else []
            test = _generate_expression_string_rapcode(node.get("test"))

            if not consequent and alternate: # Invert condition if THEN is empty
                code_lines.append(f"{indent}IF NOT {test} THEN")
                code_lines.extend(generate_rapcode_from_ast(alternate, indent_level + 1))
            else:
                code_lines.append(f"{indent}IF {test} THEN")
                code_lines.extend(generate_rapcode_from_ast(consequent, indent_level + 1))
                if alternate:
                    code_lines.append(f"{indent}ELSE")
                    code_lines.extend(generate_rapcode_from_ast(alternate, indent_level + 1))
            
            code_lines.append(f"{indent}ENDIF")

        elif node_type == "WhileStatement":
            test_expr = _generate_expression_string_rapcode(node.get("test"))
            code_lines.append(f"{indent}LOOP" if test_expr == "TRUE" else f"{indent}WHILE {test_expr} DO")
            body = node.get("body", {}).get("body", [])
            code_lines.extend(generate_rapcode_from_ast(body, indent_level + 1))
            code_lines.append(f"{indent}ENDLOOP")
            
        elif node_type == "BreakStatement":
            code_lines.append(f"{indent}BREAK")

    return '\n'.join(code_lines)

# --- BASE CLASS FOR VISUAL GENERATORS ---

class AstVisualizer:
    def __init__(self):
        self.node_count = 0
        self.loop_exit_stack = []

    def _expr_to_str(self, node):
        node_type = node.get("type")
        if node_type == "Identifier": return node["name"]
        if node_type == "Literal":
            val = node["value"]
            if isinstance(val, bool): return "TRUE" if val else "FALSE"
            return str(val)
        if node_type == "CallExpression":
            if node['callee'] == 'Input': return f'INPUT({node.get("prompt", "")})'
            args = ", ".join([self._expr_to_str(arg) for arg in node.get("arguments", [])])
            return f'{node["callee"]}({args})'
        if node_type == "BinaryExpression":
            left = self._expr_to_str(node['left'])
            right = self._expr_to_str(node['right'])
            return f"{left} {node['operator']} {right}"
        if node_type == "UnaryExpression" and node['operator'] == "NOT":
            return f"NOT {self._expr_to_str(node['argument'])}"
        return "expr"

    def _generate_from_nodes(self, nodes):
        if not nodes: return None, None
        generated = [self._generate_node(node) for node in nodes]
        for i in range(len(generated) - 1):
            exit_of_current, entry_of_next = generated[i][1], generated[i+1][0]
            if exit_of_current and entry_of_next: self._add_edge(exit_of_current, entry_of_next)
        return generated[0][0], generated[-1][1]

    def _generate_node(self, node):
        node_type = node["type"]
        if node_type == "AssignmentStatement":
            label = f"{self._expr_to_str(node['left'])} := {self._expr_to_str(node['right'])}"
            n = self._add_node(label, shape="box")
            return n, n
        if node_type == "ExpressionStatement":
            expr = node["expression"]
            if expr.get("callee") == "Output":
                label = f"OUTPUT: {self._expr_to_str(expr['arguments'][0])}"
                n = self._add_node(label, shape="parallelogram")
                return n, n
        if node_type == "BreakStatement":
            if not self.loop_exit_stack: raise ValueError("BREAK statement found outside of a loop.")
            break_entry = self._add_node(" ", shape="point")
            self._add_edge(break_entry, self.loop_exit_stack[-1])
            return break_entry, None # No exit from a break
        if node_type == "IfStatement":
            cond_node = self._add_node(self._expr_to_str(node["test"]), shape="diamond")
            merge_node = self._add_node(" ", shape="point")
            
            # True branch
            true_entry, true_exit = self._generate_from_nodes(node["consequent"]["body"])
            self._add_edge(cond_node, true_entry or merge_node, label="True")
            if true_exit: self._add_edge(true_exit, merge_node)
            
            # False branch
            alt_body = node["alternate"]["body"] if node["alternate"] else []
            false_entry, false_exit = self._generate_from_nodes(alt_body)
            self._add_edge(cond_node, false_entry or merge_node, label="False")
            if false_exit: self._add_edge(false_exit, merge_node)

            return cond_node, merge_node
        if node_type == "WhileStatement":
            entry_node = self._add_node("Loop Entry", shape="point")
            exit_node = self._add_node("Loop Exit", shape="point")
            self.loop_exit_stack.append(exit_node)

            body_entry, body_exit = self._generate_from_nodes(node["body"]["body"])
            if body_entry:
                self._add_edge(entry_node, body_entry)
                if body_exit: self._add_edge(body_exit, entry_node) # Loop back edge
            else:
                self._add_edge(entry_node, entry_node) # Empty loop
            
            self.loop_exit_stack.pop()
            return entry_node, exit_node
        return self._add_node(f"Unknown Node:\n{node_type}", shape="octagon"), None

# --- MERMAID GENERATOR ---

class MermaidGenerator(AstVisualizer):
    def generate(self, ast):
        self.node_defs, self.edge_defs = [], []
        start_node = self._add_node("Start", shape="start")
        entry, last_node = self._generate_from_nodes(ast["body"])
        self._add_edge(start_node, entry) if entry else None
        last_node = last_node or start_node
        end_node = self._add_node("End", shape="start")
        self._add_edge(last_node, end_node)
        return "graph TD;\n" + "\n".join(self.node_defs) + "\n" + "\n".join(self.edge_defs)

    def _add_node(self, label, shape, **kwargs):
        node_id = f"N{self.node_count}"; self.node_count += 1
        safe_label = label.replace('"', '#quot;')
        shapes = {"box": ('["', '"]'), "parallelogram": ('[/"', '/"]'), "diamond": ('{"', '"}'), "point": ('(("', '"))'), "start": ('("', '")')}
        shape_open, shape_close = shapes[shape]
        self.node_defs.append(f'  {node_id}{shape_open}{safe_label}{shape_close}')
        return node_id

    def _add_edge(self, from_node, to_node, label=None):
        arrow = f'--"{label}"-->' if label else '-->'
        self.edge_defs.append(f'  {from_node} {arrow} {to_node}')

# --- GRAPHVIZ (DOT) GENERATOR ---

class GraphvizGenerator(AstVisualizer):
    def generate(self, ast):
        self.dot_code = "digraph Flowchart {\n"
        self.dot_code += '  graph [splines=ortho];\n  node [fontname="Helvetica", fontsize=10, style=rounded];\n  edge [fontname="Helvetica", fontsize=9];\n'
        start_node = self._add_node("Start", shape="ellipse")
        entry, last_node = self._generate_from_nodes(ast["body"])
        self._add_edge(start_node, entry) if entry else None
        last_node = last_node or start_node
        end_node = self._add_node("End", shape="ellipse")
        self._add_edge(last_node, end_node)
        self.dot_code += "}\n"
        return self.dot_code
        
    def _add_node(self, label, shape, **kwargs):
        node_id = f"node{self.node_count}"; self.node_count += 1
        safe_label = label.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        attrs = f'label="{safe_label}", shape={shape}'
        if shape == "point": attrs += ', width="0", height="0"'
        self.dot_code += f'  {node_id} [{attrs}];\n'
        return node_id
        
    def _add_edge(self, from_node, to_node, label=None):
        attrs = f'xlabel="{label}"' if label else ""
        self.dot_code += f'  {from_node} -> {to_node} [{attrs}];\n'