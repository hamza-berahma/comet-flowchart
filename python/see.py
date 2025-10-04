import re
import sys

class RapcodeParser:
    """
    Parses .rapcode text into a structured AST. This is a simple
    recursive descent parser.
    """
    def __init__(self, code):
        self.tokens = self._tokenize(code)
        self.pos = 0

    def _tokenize(self, code):
        # This regex splits the code by spaces and parentheses, but keeps operators
        # and quoted strings intact. It uses a non-greedy match for strings to handle newlines.
        token_regex = r'\s*([A-Za-z_][A-Za-z0-9_]*|:=|==|!=|<=|>=|<|>|\*|\/|\+|-|\d+\.\d*|\d+|\"[^\"]*?\"|\(|\))\s*'
        # A more robust string regex that handles escaped quotes and newlines: r'"(?:\\.|[^"\\])*"'
        tokens = [t for t in re.findall(token_regex, code.replace('\r\n', '\n')) if t.strip()]
        return tokens

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _consume(self, expected=None):
        token = self._peek()
        if expected and token != expected:
            raise SyntaxError(f"Expected '{expected}' but found '{token}' at position {self.pos}")
        self.pos += 1
        return token
    
    def parse(self):
        statements = []
        while self._peek() is not None:
            statements.append(self._parse_statement())
        return {"type": "Program", "body": statements}

    def _parse_statement(self):
        token = self._peek()
        if token == "IF":
            return self._parse_if()
        if token == "LOOP" or token == "WHILE":
            return self._parse_loop()
        if token == "BREAK":
            self._consume("BREAK")
            return {"type": "BreakStatement"}
        if token == "OUTPUT":
            return self._parse_output()

        expr = self._parse_expression()
        if self._peek() == ":=":
            self._consume(":=")
            right = self._parse_expression()
            return {"type": "AssignmentStatement", "left": expr, "right": right}
        
        return {"type": "ExpressionStatement", "expression": expr}

    def _parse_if(self):
        self._consume("IF")
        if self._peek() == "NOT":
            self._consume("NOT")
            test = {"type": "UnaryExpression", "operator": "NOT", "argument": self._parse_expression()}
        else:
            test = self._parse_expression()
            
        self._consume("THEN")
        consequent = []
        while self._peek() not in ["ELSE", "ENDIF"]:
            consequent.append(self._parse_statement())
        
        alternate = None
        if self._peek() == "ELSE":
            self._consume("ELSE")
            alternate = []
            while self._peek() != "ENDIF":
                alternate.append(self._parse_statement())

        self._consume("ENDIF")
        return {"type": "IfStatement", "test": test, "consequent": consequent, "alternate": alternate}

    def _parse_loop(self):
        self._consume("LOOP")
        body = []
        while self._peek() != "ENDLOOP":
            body.append(self._parse_statement())
        self._consume("ENDLOOP")
        return {"type": "LoopStatement", "body": body}

    def _parse_output(self):
        self._consume("OUTPUT")
        value = self._parse_expression()
        return {"type": "OutputStatement", "value": value}

    def _parse_expression(self):
        node = self._parse_term()
        while self._peek() in ["+", "-", "*", "/", "==", "!=", "<=", ">=", "<", ">"]:
            op = self._consume()
            right = self._parse_term()
            node = {"type": "BinaryExpression", "operator": op, "left": node, "right": right}
        return node
    
    def _parse_term(self):
        token = self._peek()
        if token == "(":
            self._consume("(")
            node = self._parse_expression()
            self._consume(")")
            return node
        if token == "INPUT":
            self._consume("INPUT")
            self._consume("(")
            prompt = self._consume()
            self._consume(")")
            return {"type": "InputExpression", "prompt": prompt}
        if token.isdigit():
            return {"type": "Literal", "value": int(self._consume())}
        if token.startswith('"'):
            return {"type": "Literal", "value": self._consume()}
        if token == "TRUE":
             return {"type": "Literal", "value": True, "raw": self._consume()}
        if token == "FALSE":
             return {"type": "Literal", "value": False, "raw": self._consume()}
        return {"type": "Identifier", "name": self._consume()}


class GraphvizGenerator:
    """
    Generates a Graphviz DOT file from a .rapcode AST.
    """
    def __init__(self):
        self.dot_code = ""
        self.node_count = 0
        self.loop_exit_stack = []

    def _add_node(self, label, shape="box", **kwargs):
        node_id = f"node{self.node_count}"
        self.node_count += 1
        # Escape characters for DOT label
        safe_label = label.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        attrs = f'label="{safe_label}", shape={shape}'
        for key, value in kwargs.items():
            attrs += f', {key}="{value}"'
        self.dot_code += f'  {node_id} [{attrs}];\n'
        return node_id

    def _add_edge(self, from_node, to_node, label=None):
        if not from_node or not to_node: return
        # Use xlabel for ortho splines compatibility
        attrs = f'xlabel="{label}"' if label else ""
        self.dot_code += f'  {from_node} -> {to_node} [{attrs}];\n'

    def generate(self, ast):
        self.dot_code = "digraph Flowchart {\n"
        self.dot_code += '  graph [splines=ortho];\n'
        self.dot_code += '  node [fontname="Helvetica", fontsize=10, style=rounded];\n'
        self.dot_code += '  edge [fontname="Helvetica", fontsize=9];\n'
        
        start_node = self._add_node("Start", "ellipse")
        
        entry, last_node = self._generate_from_nodes(ast["body"])
        
        if entry:
            self._add_edge(start_node, entry)
        else: # Handle empty program
            last_node = start_node

        end_node = self._add_node("End", "ellipse")
        self._add_edge(last_node, end_node)
        
        self.dot_code += "}\n"
        return self.dot_code

    def _generate_from_nodes(self, nodes):
        """
        Generates a chain of nodes and returns the entry point of the first
        and the exit point of the last. Does not connect to any outside nodes.
        """
        if not nodes:
            return None, None
            
        # Generate all node pairs (entry, exit) first
        generated = [self._generate_node(node) for node in nodes]
        
        # Connect them in a sequential chain
        for i in range(len(generated) - 1):
            exit_of_current = generated[i][1]
            entry_of_next = generated[i+1][0]
            self._add_edge(exit_of_current, entry_of_next)
        
        # The entry to the whole chain is the entry of the first node.
        # The exit of the whole chain is the exit of the last node.
        return generated[0][0], generated[-1][1]

    def _expr_to_str(self, node):
        node_type = node.get("type")
        if node_type == "Identifier": return node["name"]
        if node_type == "Literal":
            val = node["value"]
            if isinstance(val, str) and val.startswith('"'):
                return val[1:-1] # Strip quotes for display
            if isinstance(val, bool):
                return "TRUE" if val else "FALSE"
            return str(val)
        if node_type == "InputExpression": return f"INPUT({node['prompt']})"
        if node_type == "BinaryExpression":
            left = self._expr_to_str(node['left'])
            right = self._expr_to_str(node['right'])
            return f"{left} {node['operator']} {right}"
        if node_type == "UnaryExpression" and node['operator'] == "NOT":
             return f"NOT {self._expr_to_str(node['argument'])}"
        return "expr"

    def _generate_node(self, node):
        node_type = node["type"]

        if node_type == "AssignmentStatement":
            label = f"{self._expr_to_str(node['left'])} := {self._expr_to_str(node['right'])}"
            n = self._add_node(label, "box")
            return n, n
        
        if node_type == "OutputStatement":
            label = f"OUTPUT: {self._expr_to_str(node['value'])}"
            n = self._add_node(label, "parallelogram")
            return n, n
        
        if node_type == "BreakStatement":
            break_start = self._add_node("break_start", shape="point", width="0", height="0")
            if not self.loop_exit_stack:
                raise ValueError("BREAK statement found outside of a loop.")
            self._add_edge(break_start, self.loop_exit_stack[-1])
            break_end = self._add_node("break_end", shape="point", width="0", height="0")
            return break_start, break_end

        if node_type == "IfStatement":
            cond_node = self._add_node(self._expr_to_str(node["test"]), "diamond")
            merge_node = self._add_node("", shape="point", width="0", height="0")

            # True branch
            true_entry, true_exit = self._generate_from_nodes(node["consequent"])
            if true_entry:
                self._add_edge(cond_node, true_entry, label="True")
                self._add_edge(true_exit, merge_node)
            else:
                self._add_edge(cond_node, merge_node, label="True")
            
            # False branch
            if node["alternate"]:
                false_entry, false_exit = self._generate_from_nodes(node["alternate"])
                if false_entry:
                    self._add_edge(cond_node, false_entry, label="False")
                    self._add_edge(false_exit, merge_node)
                else:
                    self._add_edge(cond_node, merge_node, label="False")
            else:
                self._add_edge(cond_node, merge_node, label="False")
            
            return cond_node, merge_node
        
        if node_type == "LoopStatement":
            entry_node = self._add_node("", shape="point", width="0", height="0")
            exit_node = self._add_node("", shape="point", width="0", height="0")
            self.loop_exit_stack.append(exit_node)

            body_entry, body_exit = self._generate_from_nodes(node["body"])
            if body_entry:
                self._add_edge(entry_node, body_entry)
                self._add_edge(body_exit, entry_node) # Loop back edge
            else:
                self._add_edge(entry_node, entry_node) # Empty loop
            
            self.loop_exit_stack.pop()
            return entry_node, exit_node

        unknown_node = self._add_node(f"Unknown Node:\n{node_type}", "octagon", style="filled", fillcolor="red")
        return unknown_node, unknown_node

def main():
    input_file = 'ticket_system.rapcode'
    output_file = 'flowchart.dot'

    try:
        with open(input_file, 'r') as f:
            code = f.read()
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
        print("Please save the provided .rapcode into that file.")
        return

    try:
        parser = RapcodeParser(code)
        ast = parser.parse()

        generator = GraphvizGenerator()
        dot_output = generator.generate(ast)

        with open(output_file, 'w') as f:
            f.write(dot_output)
        
        print(f"Successfully generated '{output_file}'.")
        print("\nTo create a PNG image from this file, run:")
        print(f"dot -Tpng {output_file} -o flowchart.png")

    except (SyntaxError, ValueError) as e:
        print(f"An error occurred: {e}", file=sys.stderr)

if __name__ == '__main__':
    main()

