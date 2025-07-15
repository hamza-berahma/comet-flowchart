import sys
from rap_to_ast import parse_rap
from ast_to_rapcode import json_to_rapcode
from ast_to_mermaid import generate_mermaid
from ast_to_cfg import generate_cfg

def main(input_file):
    ast = parse_rap(input_file)
    subchart = ast["subcharts"][0]["start_node"]

    # Save AST
    with open("output.json", "w") as f:
        import json
        json.dump(ast, f, indent=2)

    # RAPCODE
    rapcode = "\n".join(json_to_rapcode(subchart)) #to fix
    with open("output.rapcode", "w") as f:
        f.write(rapcode)

    # Mermaid Flowchart
    generate_mermaid(ast, "output.mmd")

    # CFG
    generate_cfg(ast, "cfg.png")

    print("Done: AST → .rapcode + .mmd + cfg.png")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_pipeline.py samples/factorial.rap")
    else:
        main(sys.argv[1])
