import json
import re
import xml.etree.ElementTree as ET

# Namespaces used in the Raptor XML file
# These are essential for finding elements with ET.find()
NAMESPACES = {
    '': 'http://schemas.datacontract.org/2004/07/RAPTOR_Avalonia_MVVM.ViewModels',
    'i': 'http://www.w3.org/2001/XMLSchema-instance',
    'a': 'http://schemas.datacontract.org/2004/07/raptor',
    'b': 'http://www.w3.org/2001/XMLSchema'
}

def get_node_type(xml_node):
    """
    Determines the component's semantic type, preferring the i:type attribute
    over the plain XML tag name. This handles Raptor's polymorphism.
    """
    if xml_node is None:
        return None
    
    # The 'type' attribute is in the 'i' namespace (XMLSchema-instance)
    type_attr = xml_node.get(f"{{{NAMESPACES['i']}}}type")
    
    if type_attr:
        # The attribute value is like "a:Rectangle", we just want "Rectangle"
        return type_attr.split(':')[-1]
        
    # Fallback to the tag name if i:type is not present
    return xml_node.tag.split('}')[-1]

def find_element_robust(xml_node, tag):
    """
    A robust find function that handles local namespace overrides (xmlns="").
    It first tries to find the tag with the namespace and falls back to searching
    for the local name without a namespace.
    """
    if xml_node is None:
        return None
    
    # Try finding with the full namespace prefix (e.g., 'a:_Successor')
    element = xml_node.find(tag, NAMESPACES)
    
    if element is None:
        # Fallback: find by local name for elements in a reset namespace (xmlns="")
        local_tag = tag.split(':')[-1]
        element = xml_node.find(local_tag)
        
    return element

def safe_get_text(xml_node, tag, default=''):
    """
    Safely finds an element using the robust finder and gets its text,
    returning a default if not found.
    """
    element = find_element_robust(xml_node, tag)
    if element is not None and element.text is not None:
        return element.text
    return default

def find_actual_component(container_element):
    """
    Finds the actual component node.
    Raptor XML can place the component as a child of a container (e.g., _Successor)
    or define the container itself as the component using i:type. This handles both.
    """
    if container_element is None:
        return None
    
    # Case 1: The container itself is the component (e.g., <_Successor i:type="a:Rectangle">)
    if container_element.get(f"{{{NAMESPACES['i']}}}type"):
        return container_element
    
    # Case 2: The component is the first child of the container.
    # Iterate through children to find the first actual element.
    for child in container_element:
        if isinstance(child.tag, str): # Filters out comments, etc.
            return child
    return None


def parse_literal(value_str):
    """
    Parses a string value and converts it to a Python literal (int, float, bool, or str).
    Returns a dictionary representing the AST Literal node.
    """
    value_str = value_str.strip()
    if value_str.lower() == 'true':
        return {"type": "Literal", "value": True}
    if value_str.lower() == 'false':
        return {"type": "Literal", "value": False}
    if value_str.startswith('"') and value_str.endswith('"'):
        return {"type": "Literal", "value": value_str[1:-1]}
    try:
        return {"type": "Literal", "value": int(value_str)}
    except ValueError:
        try:
            return {"type": "Literal", "value": float(value_str)}
        except ValueError:
            return {"type": "Identifier", "name": value_str}

def parse_expression(expr_str):
    """
    Parses a string expression (e.g., "x + 5", "greedy != true") into an AST node.
    Handles simple binary expressions and literals/identifiers.
    """
    expr_str = expr_str.strip()

    string_parts = re.split(r' \+ ', expr_str)
    if len(string_parts) > 1 and any(p.startswith('"') for p in string_parts):
        ast = parse_expression(string_parts[0])
        for part in string_parts[1:]:
            ast = {
                "type": "BinaryExpression",
                "operator": "+",
                "left": ast,
                "right": parse_expression(part)
            }
        return ast
        
    operators = ['!=', '<=', '>=', '==', '=', '<', '>', ':=', '+', '-', '*', '/']
    for op in operators:
        parts = expr_str.split(op, 1)
        if len(parts) == 2:
            ast_op = op
            if op == ':=':
                ast_op = "="
            elif op == '=':
                ast_op = "=="

            return {
                "type": "BinaryExpression",
                "operator": ast_op,
                "left": parse_expression(parts[0]),
                "right": parse_expression(parts[1])
            }
    
    return parse_literal(expr_str)


def parse_node(xml_node):
    """
    Recursively parses a single XML node and its successors into a list of AST nodes.
    """
    if xml_node is None or xml_node.get(f"{{{NAMESPACES['i']}}}nil") == 'true':
        return []

    node_type = get_node_type(xml_node)
    ast_nodes = []
    current_ast_node = None

    if node_type == 'Rectangle':
        text = safe_get_text(xml_node, 'a:_text_str')
        if ':=' in text:
            left, right = text.split(':=', 1)
            current_ast_node = {
                "type": "AssignmentStatement",
                "left": parse_expression(left.strip()),
                "right": parse_expression(right.strip())
            }
        else:
            print(f"Warning: Unhandled Rectangle content: {text}")

    elif node_type == 'Parallelogram':
        is_input = safe_get_text(xml_node, 'a:_is_input', 'false').lower() == 'true'
        text_str = safe_get_text(xml_node, 'a:_text_str')
        
        if is_input:
            prompt_text = safe_get_text(xml_node, 'a:_prompt')
            current_ast_node = {
                "type": "AssignmentStatement",
                "left": {"type": "Identifier", "name": text_str.strip()},
                "right": { "type": "CallExpression", "callee": "Input", "prompt": prompt_text }
            }
        else:
            current_ast_node = {
                "type": "ExpressionStatement",
                "expression": {
                    "type": "CallExpression",
                    "callee": "Output",
                    "arguments": [parse_expression(text_str)]
                }
            }
            
    elif node_type == 'IF_Control':
        text = safe_get_text(xml_node, 'a:_text_str')
        left_child_container = find_element_robust(xml_node, 'a:_left_Child')
        right_child_container = find_element_robust(xml_node, 'a:_right_Child')
        
        current_ast_node = {
            "type": "IfStatement",
            "test": parse_expression(text),
            "consequent": { "type": "BlockStatement", "body": parse_node(find_actual_component(left_child_container)) },
            "alternate": { "type": "BlockStatement", "body": parse_node(find_actual_component(right_child_container)) }
        }
        
    elif node_type == 'Loop':
        # Get the loop's exit condition text
        text = safe_get_text(xml_node, 'a:_text_str')
        
        # Find the containers for the code before and after the condition check
        before_child_container = find_element_robust(xml_node, 'a:_before_Child')
        after_child_container = find_element_robust(xml_node, 'a:_after_Child')
        
        # Parse the statements that execute before and after the condition check
        before_body = parse_node(find_actual_component(before_child_container))
        after_body = parse_node(find_actual_component(after_child_container))

        # The condition in Raptor is the EXIT condition.
        # We model this as an 'if (condition) { break; }' statement.
        exit_condition_ast = parse_expression(text)
        if_break_node = {
            "type": "IfStatement",
            "test": exit_condition_ast,
            "consequent": {"type": "BlockStatement", "body": [{"type": "BreakStatement"}]},
            "alternate": None
        }

        # This correctly models a mid-test loop by placing the exit condition
        # between the 'before' and 'after' code blocks. This also handles
        # pre-test (empty 'before_body') and post-test (empty 'after_body') cases.
        loop_body_statements = before_body + [if_break_node] + after_body
        
        # Create a 'while True' loop in the AST
        current_ast_node = {
            "type": "WhileStatement",
            "test": {"type": "Literal", "value": True},
            "body": {
                "type": "BlockStatement",
                "body": loop_body_statements
            }
        }

    if current_ast_node:
        ast_nodes.append(current_ast_node)

    successor_container = find_element_robust(xml_node, 'a:_Successor')
    successor_node = find_actual_component(successor_container)
    if successor_node is not None:
        ast_nodes.extend(parse_node(successor_node))
    
    return ast_nodes


def convert_raptor_to_ast(xml_file_path):
    """
    Main function to load a Raptor XML file and convert it to a JSON AST.
    """
    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()

        start_node = root.find('.//a:Start', NAMESPACES)
        if start_node is None:
            return {"error": "Could not find the <Start> node in the XML file."}

        successor_container = find_element_robust(start_node, 'a:_Successor')
        first_node = find_actual_component(successor_container)

        body = parse_node(first_node)
        
        program_ast = { "type": "Program", "body": body }
        return program_ast

    except ET.ParseError as e:
        return {"error": f"XML Parse Error: {e}"}
    except FileNotFoundError:
        return {"error": f"File not found: {xml_file_path}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}", "details": str(e)}


if __name__ == '__main__':
    # You would need a 'factorial.rap' file for this to run.
    xml_file = 'factorial.rap' 
    output_json_file = 'flowchart.json'
    
    try:
        with open(xml_file, 'r', encoding='utf-8') as f:
            pass
    except FileNotFoundError:
        print(f"'{xml_file}' not found. Please create this file with your Raptor XML content.")
        # As an example, create a dummy file if it doesn't exist
        with open(xml_file, 'w', encoding='utf-8') as f:
            f.write('<!-- Replace this with your Raptor XML content -->')
        print(f"A dummy '{xml_file}' has been created.")
        exit()
        
    ast_representation = convert_raptor_to_ast(xml_file)

    # Write the output to flowchart.json
    with open(output_json_file, 'w', encoding='utf-8') as f:
        json.dump(ast_representation, f, indent=2)
    
    print(f"AST has been successfully generated and saved to '{output_json_file}'.")

