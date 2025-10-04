import json
import os

def generate_expression_string_rapcode(node):
    """
    Recursively builds a code string from an expression AST node for .rapcode syntax.
    """
    if node is None: return ""
    node_type = node.get("type")

    if node_type == "Literal":
        value = node.get("value")
        if isinstance(value, str):
            return f'"{value}"'
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        return str(value)
        
    elif node_type == "Identifier":
        return node.get("name", "")
        
    elif node_type == "BinaryExpression":
        left = generate_expression_string_rapcode(node.get("left"))
        right = generate_expression_string_rapcode(node.get("right"))
        operator = node.get("operator", "")
        return f"({left} {operator} {right})"

    elif node_type == "CallExpression" and node.get("callee") == "Input":
        prompt_literal = node.get("prompt", '""')
        return f'INPUT({prompt_literal})'
        
    return ""

def generate_rapcode_from_ast(ast_nodes, indent_level=0):
    """
    Recursively traverses the AST and generates formatted .rapcode lines
    with an ANTLR4-friendly syntax.
    """
    code_lines = []
    indent = "  " * indent_level

    for node in ast_nodes:
        node_type = node.get("type")

        if node_type == "AssignmentStatement":
            left = generate_expression_string_rapcode(node.get("left"))
            right_node = node.get("right")
            right = generate_expression_string_rapcode(right_node)
            code_lines.append(f'{indent}{left} := {right}')

        elif node_type == "ExpressionStatement":
            expression = node.get("expression", {})
            if expression.get("callee") == "Output":
                arg_node = expression.get("arguments", [])[0]
                arg_string = generate_expression_string_rapcode(arg_node)
                code_lines.append(f'{indent}OUTPUT {arg_string}')

        elif node_type == "IfStatement":
            consequent_block = node.get("consequent")
            consequent = consequent_block.get("body", []) if consequent_block else []
            
            alternate_block = node.get("alternate")
            alternate = alternate_block.get("body", []) if alternate_block else []

            # Better logic: Invert the condition if the THEN block is empty and ELSE is not.
            if not consequent and alternate:
                test = generate_expression_string_rapcode(node.get("test"))
                code_lines.append(f"{indent}IF NOT {test} THEN")
                code_lines.extend(generate_rapcode_from_ast(alternate, indent_level + 1))
                code_lines.append(f"{indent}ENDIF")
            else:
                test = generate_expression_string_rapcode(node.get("test"))
                code_lines.append(f"{indent}IF {test} THEN")
                code_lines.extend(generate_rapcode_from_ast(consequent, indent_level + 1))
                if alternate:
                    code_lines.append(f"{indent}ELSE")
                    code_lines.extend(generate_rapcode_from_ast(alternate, indent_level + 1))
                code_lines.append(f"{indent}ENDIF")

        elif node_type == "WhileStatement":
            test_expr = generate_expression_string_rapcode(node.get("test"))
            
            if test_expr == "TRUE": # Handles 'while True'
                 code_lines.append(f"{indent}LOOP")
            else:
                 code_lines.append(f"{indent}WHILE {test_expr} DO")
                 
            body = node.get("body", {}).get("body", [])
            code_lines.extend(generate_rapcode_from_ast(body, indent_level + 1))
            code_lines.append(f"{indent}ENDLOOP")

        elif node_type == "BreakStatement":
            code_lines.append(f"{indent}BREAK")
            
        elif node_type == "BlockStatement":
            code_lines.extend(generate_rapcode_from_ast(node.get("body", []), indent_level))

    return code_lines

def main():
    """ Reads the AST, generates .rapcode, and saves it to a file. """
    input_json_file = 'flowchart.json'
    output_code_file = 'generated_code.rapcode'

    if not os.path.exists(input_json_file):
        print(f"Error: Input file '{input_json_file}' not found.")
        return

    with open(input_json_file, 'r', encoding='utf-8') as f:
        ast_data = json.load(f)
    if "error" in ast_data:
        print(f"The AST file contains an error: {ast_data['error']}")
        return

    generated_code = generate_rapcode_from_ast(ast_data.get("body", []))
    with open(output_code_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(generated_code))
    print(f"Code has been successfully generated and saved to '{output_code_file}'.")

if __name__ == '__main__':
    main()

