import json
import sys
import os

def load_ast(filename="output.json"):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def write_rapcode(lines, filename="output.rapcode"):
    with open(filename, "w", encoding="utf-8") as f:
        f.writelines(line + "\n" for line in lines)

def ast_to_rapcode(node, indent=0, in_main_block=False):
    if not node:
        return []

    IND = "  " * indent
    lines = []

    node_type = node.get("node_type")
    text = node.get("text", "")
    children = node.get("children", [])
    attrs = node.get("attributes", {})

    def recurse(child_list):
        return [line for child in child_list if child for line in ast_to_rapcode(child, indent, in_main_block)]

    if node_type == "Start":
        lines.append(f"{IND}START")
        if children:
            lines += ast_to_rapcode(children[0], indent + 1, in_main_block=True)
        lines.append(f"{IND}END")

    elif node_type == "End":
        pass

    elif node_type == "Input":
        var = attrs.get("variable", text.split()[-1])
        prompt = text.replace(var, "").strip().strip('"') or var
        lines.append(f'{IND}INPUT {var} "{prompt}"')
        lines += recurse(children)

    elif node_type == "Output":
        lines.append(f"{IND}OUTPUT {text}")
        lines += recurse(children)

    elif node_type == "Assignment":
        if ":=" in text:
            var, expr = map(str.strip, text.split(":=", 1))
        elif "=" in text:
            var, expr = map(str.strip, text.split("=", 1))
        else:
            var, expr = text.strip(), ""
        lines.append(f"{IND}SET {var} := {expr}")
        lines += recurse(children)

    elif node_type == "If":
        cond = text.strip()
        lines.append(f"{IND}IF {cond}")

        then_branch = next((c for c in children if c.get("attributes", {}).get("branch") == "then"), None)
        else_branch = next((c for c in children if c.get("attributes", {}).get("branch") == "else"), None)

        if then_branch:
            lines += ast_to_rapcode(then_branch, indent + 1, in_main_block)
        if else_branch:
            lines.append(f"{IND}ELSE")
            lines += ast_to_rapcode(else_branch, indent + 1, in_main_block)

        lines.append(f"{IND}ENDIF")

        other_children = [
            c for c in children if c and c.get("attributes", {}).get("branch") not in {"then", "else"}
        ]
        lines += recurse(other_children)

    elif node_type == "Loop":
        cond = text.strip() or "TRUE"
        lines.append(f"{IND}LOOP {cond}")

        body = next((c for c in children if c.get("attributes", {}).get("loop_part") == "body"), None)
        if body:
            lines += ast_to_rapcode(body, indent + 1, in_main_block)
        lines.append(f"{IND}ENDLOOP")

        other_children = [
            c for c in children if c and c.get("attributes", {}).get("loop_part") != "body"
        ]
        lines += recurse(other_children)

    elif node_type is None:
        pass  

    else:
        if text.strip():
            lines.append(f"{IND}# {node_type}: {text.strip()}")
        lines += recurse(children)

    return [line for line in lines if line.strip()]


def main():
    if len(sys.argv) < 2:
        print("Usage: python script.py <input_file.json>")
        return

    input_file = sys.argv[1]
    
    if not os.path.exists(input_file):
        print(f"Error: file '{input_file}' not found.")
        return

    if not input_file.endswith(".json"):
        print("Error: input file must be a .json file.")
        return

    output_file = input_file.replace(".json", ".rapcode")

    ast = load_ast(input_file)
    rapcode_lines = ast_to_rapcode(ast)
    write_rapcode(rapcode_lines, output_file)

    print(f"{output_file} written.")

if __name__ == "__main__":
    main()
