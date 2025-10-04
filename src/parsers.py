import json
import re
import xml.etree.ElementTree as ET

# --- RAPTOR XML TO AST PARSER ---

NAMESPACES = {
    '': 'http://schemas.datacontract.org/2004/07/RAPTOR_Avalonia_MVVM.ViewModels',
    'i': 'http://www.w3.org/2001/XMLSchema-instance',
    'a': 'http://schemas.datacontract.org/2004/07/raptor',
    'b': 'http://www.w3.org/2001/XMLSchema'
}

def _get_node_type(xml_node):
    if xml_node is None: return None
    type_attr = xml_node.get(f"{{{NAMESPACES['i']}}}type")
    if type_attr: return type_attr.split(':')[-1]
    return xml_node.tag.split('}')[-1]

def _find_element_robust(xml_node, tag):
    if xml_node is None: return None
    element = xml_node.find(tag, NAMESPACES)
    if element is None:
        local_tag = tag.split(':')[-1]
        element = xml_node.find(local_tag)
    return element

def _safe_get_text(xml_node, tag, default=''):
    element = _find_element_robust(xml_node, tag)
    return element.text if element is not None and element.text is not None else default

def _find_actual_component(container_element):
    if container_element is None: return None
    if container_element.get(f"{{{NAMESPACES['i']}}}type"): return container_element
    for child in container_element:
        if isinstance(child.tag, str): return child
    return None

def _parse_literal(value_str):
    value_str = value_str.strip()
    if value_str.lower() == 'true': return {"type": "Literal", "value": True}
    if value_str.lower() == 'false': return {"type": "Literal", "value": False}
    if value_str.startswith('"') and value_str.endswith('"'): return {"type": "Literal", "value": value_str[1:-1]}
    try: return {"type": "Literal", "value": int(value_str)}
    except ValueError:
        try: return {"type": "Literal", "value": float(value_str)}
        except ValueError: return {"type": "Identifier", "name": value_str}

def _parse_expression_from_raptor(expr_str):
    expr_str = expr_str.strip()
    string_parts = re.split(r' \+ ', expr_str)
    if len(string_parts) > 1 and any(p.startswith('"') for p in string_parts):
        ast = _parse_expression_from_raptor(string_parts[0])
        for part in string_parts[1:]:
            ast = {"type": "BinaryExpression", "operator": "+", "left": ast, "right": _parse_expression_from_raptor(part)}
        return ast
        
    operators = ['!=', '<=', '>=', '==', '=', '<', '>', ':=', '+', '-', '*', '/']
    for op in operators:
        parts = expr_str.split(op, 1)
        if len(parts) == 2:
            ast_op = op if op != ':=' else "="
            if op == '=': ast_op = "=="
            return {"type": "BinaryExpression", "operator": ast_op, "left": _parse_expression_from_raptor(parts[0]), "right": _parse_expression_from_raptor(parts[1])}
    return _parse_literal(expr_str)

def _parse_raptor_node(xml_node):
    if xml_node is None or xml_node.get(f"{{{NAMESPACES['i']}}}nil") == 'true': return []
    node_type = _get_node_type(xml_node)
    ast_nodes = []
    current_ast_node = None
    if node_type == 'Rectangle':
        text = _safe_get_text(xml_node, 'a:_text_str')
        if ':=' in text:
            left, right = text.split(':=', 1)
            current_ast_node = {"type": "AssignmentStatement", "left": _parse_expression_from_raptor(left.strip()), "right": _parse_expression_from_raptor(right.strip())}
    elif node_type == 'Parallelogram':
        is_input = _safe_get_text(xml_node, 'a:_is_input', 'false').lower() == 'true'
        text_str = _safe_get_text(xml_node, 'a:_text_str')
        if is_input:
            prompt_text = _safe_get_text(xml_node, 'a:_prompt')
            current_ast_node = {"type": "AssignmentStatement", "left": {"type": "Identifier", "name": text_str.strip()}, "right": {"type": "CallExpression", "callee": "Input", "prompt": prompt_text}}
        else:
            current_ast_node = {"type": "ExpressionStatement", "expression": {"type": "CallExpression", "callee": "Output", "arguments": [_parse_expression_from_raptor(text_str)]}}
    elif node_type == 'IF_Control':
        text = _safe_get_text(xml_node, 'a:_text_str')
        left_child_container = _find_element_robust(xml_node, 'a:_left_Child')
        right_child_container = _find_element_robust(xml_node, 'a:_right_Child')
        current_ast_node = {"type": "IfStatement", "test": _parse_expression_from_raptor(text), "consequent": {"type": "BlockStatement", "body": _parse_raptor_node(_find_actual_component(left_child_container))}, "alternate": {"type": "BlockStatement", "body": _parse_raptor_node(_find_actual_component(right_child_container))}}
    elif node_type == 'Loop':
        text = _safe_get_text(xml_node, 'a:_text_str')
        before_child_container = _find_element_robust(xml_node, 'a:_before_Child')
        after_child_container = _find_element_robust(xml_node, 'a:_after_Child')
        before_body = _parse_raptor_node(_find_actual_component(before_child_container))
        after_body = _parse_raptor_node(_find_actual_component(after_child_container))
        if_break_node = {"type": "IfStatement", "test": _parse_expression_from_raptor(text), "consequent": {"type": "BlockStatement", "body": [{"type": "BreakStatement"}]}, "alternate": None}
        loop_body_statements = before_body + [if_break_node] + after_body
        current_ast_node = {"type": "WhileStatement", "test": {"type": "Literal", "value": True}, "body": {"type": "BlockStatement", "body": loop_body_statements}}
    if current_ast_node: ast_nodes.append(current_ast_node)
    successor_container = _find_element_robust(xml_node, 'a:_Successor')
    successor_node = _find_actual_component(successor_container)
    if successor_node is not None: ast_nodes.extend(_parse_raptor_node(successor_node))
    return ast_nodes

def parse_raptor_xml(file_path):
    """Loads a Raptor XML file and returns a JSON AST."""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        start_node = root.find('.//a:Start', NAMESPACES)
        if start_node is None: raise ValueError("Could not find the <Start> node in the XML file.")
        successor_container = _find_element_robust(start_node, 'a:_Successor')
        first_node = _find_actual_component(successor_container)
        body = _parse_raptor_node(first_node)
        return {"type": "Program", "body": body}
    except ET.ParseError as e: raise ValueError(f"XML Parse Error: {e}")
    except FileNotFoundError: raise FileNotFoundError(f"File not found: {file_path}")


# --- RAPCODE TO AST PARSER ---

class RapcodeParser:
    """Parses .rapcode text into a structured AST."""
    def __init__(self, code):
        self.tokens = self._tokenize(code)
        self.pos = 0

    def _tokenize(self, code):
        token_regex = r'\s*([A-Za-z_][A-Za-z0-9_]*|:=|==|!=|<=|>=|<|>|\*|\/|\+|-|\d+\.\d*|\d+|\"[^\"]*?\"|\(|\))\s*'
        return [t for t in re.findall(token_regex, code.replace('\r\n', '\n')) if t.strip()]

    def _peek(self): return self.tokens[self.pos] if self.pos < len(self.tokens) else None
    def _consume(self, expected=None):
        token = self._peek()
        if expected and token != expected: raise SyntaxError(f"Expected '{expected}' but found '{token}' at position {self.pos}")
        self.pos += 1
        return token
    
    def parse(self):
        statements = []
        while self._peek() is not None: statements.append(self._parse_statement())
        return {"type": "Program", "body": statements}

    def _parse_statement(self):
        token = self._peek()
        if token == "IF": return self._parse_if()
        if token == "LOOP" or token == "WHILE": return self._parse_loop()
        if token == "BREAK": self._consume("BREAK"); return {"type": "BreakStatement"}
        if token == "OUTPUT": return self._parse_output()
        expr = self._parse_expression()
        if self._peek() == ":=":
            self._consume(":=")
            right = self._parse_expression()
            return {"type": "AssignmentStatement", "left": expr, "right": right}
        return {"type": "ExpressionStatement", "expression": expr}

    def _parse_if(self):
        self._consume("IF")
        test = self._parse_expression()
        self._consume("THEN")
        consequent_body = []
        while self._peek() not in ["ELSE", "ENDIF"]: consequent_body.append(self._parse_statement())
        
        alternate_body = []
        if self._peek() == "ELSE":
            self._consume("ELSE")
            while self._peek() != "ENDIF": alternate_body.append(self._parse_statement())
        self._consume("ENDIF")
        
        return {
            "type": "IfStatement", 
            "test": test, 
            "consequent": {"type": "BlockStatement", "body": consequent_body}, 
            "alternate": {"type": "BlockStatement", "body": alternate_body} if alternate_body else None
        }

    def _parse_loop(self):
        self._consume("LOOP") # Simplified to only handle LOOP/ENDLOOP for now
        body = []
        while self._peek() != "ENDLOOP": body.append(self._parse_statement())
        self._consume("ENDLOOP")
        return {
            "type": "WhileStatement", 
            "test": {"type": "Literal", "value": True}, 
            "body": {"type": "BlockStatement", "body": body}
        }

    def _parse_output(self):
        self._consume("OUTPUT")
        arg_node = self._parse_expression()
        return {
            "type": "ExpressionStatement", 
            "expression": {"type": "CallExpression", "callee": "Output", "arguments": [arg_node]}
        }

    def _parse_expression(self):
        node = self._parse_term()
        while self._peek() in ["+", "-", "*", "/", "==", "!=", "<=", ">=", "<", ">"]:
            op = self._consume()
            right = self._parse_term()
            node = {"type": "BinaryExpression", "operator": op, "left": node, "right": right}
        return node
    
    def _parse_term(self):
        token = self._peek()
        if token == "(": self._consume("("); node = self._parse_expression(); self._consume(")"); return node
        if token == "INPUT":
            self._consume("INPUT"); self._consume("("); prompt_node = self._parse_expression(); self._consume(")")
            # Standardize INPUT to match the Raptor AST structure
            prompt_literal = prompt_node.get("value", '""')
            return {"type": "CallExpression", "callee": "Input", "prompt": f'"{prompt_literal}"'}
        if token.isdigit(): return {"type": "Literal", "value": int(self._consume())}
        if token.startswith('"'): return {"type": "Literal", "value": self._consume()[1:-1]}
        if token == "TRUE": self._consume(); return {"type": "Literal", "value": True}
        if token == "FALSE": self._consume(); return {"type": "Literal", "value": False}
        return {"type": "Identifier", "name": self._consume()}

def parse_rapcode(code):
    """Parses a string of .rapcode and returns a JSON AST."""
    parser = RapcodeParser(code)
    return parser.parse()

