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


class MermaidGenerator:
    """
    Generates a Mermaid flowchart string from a .rapcode AST.
    """
    def __init__(self):
        self.node_defs = []
        self.edge_defs = []
        self.node_count = 0
        self.loop_exit_stack = []

    def _get_node_id(self):
        node_id = f"N{self.node_count}"
        self.node_count += 1
        return node_id

    def _add_node(self, label, shape_open, shape_close):
        node_id = self._get_node_id()
        # Mermaid labels need quotes and special chars escaped
        safe_label = label.replace('"', '#quot;')
        self.node_defs.append(f'  {node_id}{shape_open}"{safe_label}"{shape_close}')
        return node_id

    def _add_edge(self, from_node, to_node, label=None):
        if not from_node or not to_node: return
        arrow = f'--"{label}"-->' if label else '-->'
        self.edge_defs.append(f'  {from_node} {arrow} {to_node}')

    def generate(self, ast):
        # The main generation logic remains the same, returning entry/exit pairs
        start_node = self._add_node("Start", "(", ")")
        
        entry, last_node = self._generate_from_nodes(ast["body"])
        
        if entry:
            self._add_edge(start_node, entry)
        else: # Handle empty program
            last_node = start_node

        end_node = self._add_node("End", "(", ")")
        self._add_edge(last_node, end_node)
        
        # Assemble the final Mermaid string
        header = "graph TD;\n"
        return header + "\n".join(self.node_defs) + "\n" + "\n".join(self.edge_defs)

    def _generate_from_nodes(self, nodes):
        if not nodes:
            return None, None
            
        generated = [self._generate_node(node) for node in nodes]
        
        for i in range(len(generated) - 1):
            exit_of_current = generated[i][1]
            entry_of_next = generated[i+1][0]
            if exit_of_current and entry_of_next:
                 self._add_edge(exit_of_current, entry_of_next)
        
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
            n = self._add_node(label, "[", "]") # Rectangle
            return n, n
        
        if node_type == "OutputStatement":
            label = f"OUTPUT: {self._expr_to_str(node['value'])}"
            n = self._add_node(label, "[/", "/]") # Parallelogram
            return n, n
        
        if node_type == "BreakStatement":
            if not self.loop_exit_stack:
                raise ValueError("BREAK statement found outside of a loop.")
            
            # Create a small, invisible node to represent the entry point of the break action.
            # This is where the preceding statement will connect.
            break_entry_node = self._add_node(" ", "((", "))")
            
            # This node immediately redirects flow to the loop's designated exit point.
            self._add_edge(break_entry_node, self.loop_exit_stack[-1])
            
            # The exit of the break itself is None, as it terminates the flow within its current block.
            return break_entry_node, None


        if node_type == "IfStatement":
            cond_node = self._add_node(self._expr_to_str(node["test"]), "{", "}") # Diamond
            merge_node = self._add_node(" ", "((", "))") # Small circle for merging

            # True branch
            true_entry, true_exit = self._generate_from_nodes(node["consequent"])
            self._add_edge(cond_node, true_entry or merge_node, label="True")
            if true_exit:
                self._add_edge(true_exit, merge_node)
            
            # False branch
            if node["alternate"]:
                false_entry, false_exit = self._generate_from_nodes(node["alternate"])
                self._add_edge(cond_node, false_entry or merge_node, label="False")
                if false_exit:
                    self._add_edge(false_exit, merge_node)
            else:
                self._add_edge(cond_node, merge_node, label="False")
            
            return cond_node, merge_node
        
        if node_type == "LoopStatement":
            entry_node = self._add_node("Loop", "((", "))")
            exit_node = self._add_node(" ", "((", "))") # Exit point for breaks
            self.loop_exit_stack.append(exit_node)

            body_entry, body_exit = self._generate_from_nodes(node["body"])
            if body_entry:
                self._add_edge(entry_node, body_entry)
                if body_exit: # If body doesn't end in a break
                    self._add_edge(body_exit, entry_node) # Loop back edge
            else:
                self._add_edge(entry_node, entry_node) # Empty loop
            
            self.loop_exit_stack.pop()
            return entry_node, exit_node

        # Fallback for unknown node types
        unknown_node = self._add_node(f"Unknown Node:\n{node_type}", "[", "]")
        return unknown_node, unknown_node

def main():
    input_file = 'ticket_system.rapcode'
    output_file = 'flowchart.mmd' # Changed output file

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

        generator = MermaidGenerator()
        mermaid_output = generator.generate(ast)

        with open(output_file, 'w') as f:
            f.write(mermaid_output)
        
        print(f"Successfully generated '{output_file}'.")
        print("\nYou can paste its content into a Mermaid-compatible editor to see the flowchart.")

    except (SyntaxError, ValueError) as e:
        print(f"An error occurred: {e}", file=sys.stderr)

if __name__ == '__main__':
    main()

