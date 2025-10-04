import sys
import argparse
from antlr4 import *
from generated.RapcodeLexer import RapcodeLexer
from generated.RapcodeParser import RapcodeParser
from interpreter import RapcodeInterpreter, RapcodeError

def main():
    """
    The main entry point for the Rapcode interpreter.
    Sets up argument parsing and the ANTLR pipeline.
    """
    parser = argparse.ArgumentParser(description="A robust interpreter for the Rapcode language.")
    parser.add_argument("file", help="The .rapcode file to execute.")
    args = parser.parse_args()

    input_file = args.file
    try:
        # Use a FileStream to read the source code from the specified file
        input_stream = FileStream(input_file, encoding='utf-8')
    except FileNotFoundError:
        print(f"[File Error] The file '{input_file}' was not found.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[File Error] Could not read file '{input_file}': {e}", file=sys.stderr)
        sys.exit(1)

    # --- ANTLR Pipeline ---
    lexer = RapcodeLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = RapcodeParser(stream)
    
    # Set a custom error listener for syntax errors if needed (optional enhancement)
    # parser.removeErrorListeners() 
    # parser.addErrorListener(MyErrorListener())

    tree = parser.program()

    # --- Interpretation ---
    interpreter = RapcodeInterpreter()
    try:
        interpreter.visit(tree)
    except RapcodeError as e:
        # Catch our custom, clean runtime errors and print them.
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Catch any other unexpected errors during interpretation.
        print(f"[Interpreter Crash] An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()

