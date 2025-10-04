import argparse
import os
import sys
from parsers import parse_raptor_xml, parse_rapcode
from generators import generate_rapcode_from_ast, MermaidGenerator, GraphvizGenerator

def main():
    """Main function to run the flowchart conversion tool."""
    parser = argparse.ArgumentParser(
        description="A tool to convert between Raptor flowcharts, .rapcode, and visual formats.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    # --- Arguments ---
    parser.add_argument("input_file", help="Path to the input file (.rap or .rapcode).")
    parser.add_argument(
        "--to",
        dest="output_format",
        required=True,
        choices=["rapcode", "mermaid", "dot"],
        help="The desired output format."
    )
    parser.add_argument(
        "-o", "--output",
        dest="output_file",
        help="Path to the output file. If not provided, it will be generated based on the input file name."
    )

    args = parser.parse_args()

    # --- Determine input type and parse to AST ---
    try:
        if args.input_file.endswith(".rap"):
            ast = parse_raptor_xml(args.input_file)
        elif args.input_file.endswith(".rapcode"):
            with open(args.input_file, 'r', encoding='utf-8') as f:
                code = f.read()
            ast = parse_rapcode(code)
        else:
            print(f"Error: Unknown input file type for '{args.input_file}'. Please use .rap or .rapcode.", file=sys.stderr)
            sys.exit(1)
    except (ValueError, SyntaxError, FileNotFoundError) as e:
        print(f"Error parsing input file: {e}", file=sys.stderr)
        sys.exit(1)

    # --- Generate the desired output from the AST ---
    output_content = ""
    if args.output_format == "rapcode":
        output_content = generate_rapcode_from_ast(ast.get("body", []))
    elif args.output_format == "mermaid":
        generator = MermaidGenerator()
        output_content = generator.generate(ast)
    elif args.output_format == "dot":
        generator = GraphvizGenerator()
        output_content = generator.generate(ast)
    
    # --- Determine output file path and save ---
    if args.output_file:
        output_path = args.output_file
    else:
        base_name = os.path.splitext(args.input_file)[0]
        ext_map = {"mermaid": "mmd", "dot": "dot", "rapcode": "rapcode"}
        extension = ext_map.get(args.output_format)
        output_path = f"{base_name}_converted.{extension}"

    try:
        # This line ensures the file is saved correctly without "dead" space
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(output_content)
        print(f"✅ Successfully converted '{args.input_file}' to '{output_path}'.")
    except IOError as e:
        print(f"Error writing to output file: {e}", file=sys.stderr)
        sys.exit(1)
        
if __name__ == '__main__':
    main()