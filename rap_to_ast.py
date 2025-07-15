#!/usr/bin/env python3
"""
RAPTOR to AST Parser - Extracted AST Part
========================================

This script parses RAPTOR (.rap) XML flowchart files into an Abstract Syntax Tree (AST)
and outputs the AST structure as JSON into output.txt.

Usage:
    python raptor_ast_only.py input.rap

Author: Refactored from Enhanced RAPTOR Parser
"""

import xml.etree.ElementTree as ET
import re
import json
from pathlib import Path
from typing import Optional, Dict, Set, List, Any, Union
from dataclasses import dataclass, field
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ASTNode:
    """
    Represents a node in the Abstract Syntax Tree for RAPTOR flowcharts.
    """
    node_type: str
    text: str = ''
    children: List['ASTNode'] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    node_id: Optional[str] = None
    
    def __post_init__(self):
        """Clean up text after initialization."""
        self.text = self.text.strip()
    
    def add_child(self, child: Optional['ASTNode']) -> None:
        """Add a child node if it's not None."""
        if child is not None:
            self.children.append(child)
    
    def get_all_variables(self) -> Set[str]:
        """
        Extract all variable names from this node and its children.
        
        Returns:
            Set of variable names found in the AST.
        """
        variables = set()
        var_regex = r'\b[a-zA-Z_][a-zA-Z0-9_]*\b'
        
        # Replace assignment operators for better parsing
        text_to_scan = self.text.replace(":=", " = ")
        potential_vars = re.findall(var_regex, text_to_scan)
        
        # Filter out common keywords and functions
        keywords = {
            'and', 'or', 'not', 'true', 'false', 'pi', 'sqrt', 'log', 'abs', 
            'cos', 'sin', 'tan', 'if', 'then', 'else', 'while', 'for', 'do',
            'input', 'output', 'print', 'read', 'write'
        }
        
        for var in potential_vars:
            if var.lower() not in keywords:
                variables.add(var)
        
        # Recursively get variables from children
        for child in self.children:
            variables.update(child.get_all_variables())
        
        return variables
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the AST node to a dictionary representation."""
        return {
            'node_type': self.node_type,
            'text': self.text,
            'attributes': self.attributes,
            'node_id': self.node_id,
            'children': [child.to_dict() for child in self.children]
        }
    
    def pretty_print(self, indent: int = 0) -> str:
        """Generate a pretty-printed string representation of the AST."""
        prefix = "  " * indent
        result = f"{prefix}{self.node_type}"
        
        if self.text:
            result += f": {self.text}"
        
        if self.attributes:
            attrs = ", ".join(f"{k}={v}" for k, v in self.attributes.items())
            result += f" [{attrs}]"
        
        result += "\n"
        
        for child in self.children:
            result += child.pretty_print(indent + 1)
        
        return result
    
    def __str__(self) -> str:
        return self.pretty_print()


class RaptorParserError(Exception):
    """Custom exception for RAPTOR parser errors."""
    pass


class RaptorParser:
    """
    Parser for RAPTOR flowchart XML files.
    
    This parser converts RAPTOR XML files into an Abstract Syntax Tree (AST)
    representation that can be used for analysis and code generation.
    """
    
    def __init__(self, debug: bool = False):
        """
        Initialize the parser.
        
        Args:
            debug: Enable debug logging if True.
        """
        self.parsed_nodes: Dict[str, ASTNode] = {}
        self.debug = debug
        if debug:
            logger.setLevel(logging.DEBUG)
    
    def parse_file(self, filepath: Union[str, Path]) -> Optional[ASTNode]:
        """
        Parse a RAPTOR file and return the AST root node.
        
        Args:
            filepath: Path to the RAPTOR (.rap) file.
            
        Returns:
            Root ASTNode if successful, None otherwise.
            
        Raises:
            RaptorParserError: If file cannot be parsed.
        """
        file_path = Path(filepath)
        
        if not file_path.exists():
            raise RaptorParserError(f"File not found: {filepath}")
        
        if not file_path.suffix.lower() == '.rap':
            logger.warning(f"File {filepath} doesn't have .rap extension")
        
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            
            # Find the Start node
            start_element = root.find('.//{*}Start')
            if start_element is None:
                raise RaptorParserError("No <Start> node found in the RAPTOR file")
            
            logger.info(f"Successfully parsed RAPTOR file: {filepath}")
            return self._parse_node(start_element)
            
        except ET.ParseError as e:
            raise RaptorParserError(f"XML parsing error: {e}")
        except Exception as e:
            raise RaptorParserError(f"Unexpected error parsing file: {e}")
    
    def parse_from_string(self, xml_string: str) -> Optional[ASTNode]:
        """
        Parse RAPTOR XML from a string.
        
        Args:
            xml_string: XML content as string.
            
        Returns:
            Root ASTNode if successful, None otherwise.
        """
        try:
            root = ET.fromstring(xml_string)
            start_element = root.find('.//{*}Start')
            if start_element is None:
                raise RaptorParserError("No <Start> node found in the XML")
            return self._parse_node(start_element)
        except ET.ParseError as e:
            raise RaptorParserError(f"XML parsing error: {e}")
    
    def clear_cache(self) -> None:
        """Clear the parsed nodes cache."""
        self.parsed_nodes.clear()
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get parsing statistics.
        
        Returns:
            Dictionary with parsing statistics.
        """
        if not self.parsed_nodes:
            return {"total_nodes": 0, "node_types": {}}
        
        node_types = {}
        for node in self.parsed_nodes.values():
            node_types[node.node_type] = node_types.get(node.node_type, 0) + 1
        
        return {
            "total_nodes": len(self.parsed_nodes),
            "node_types": node_types
        }
    
    def _clean_tag(self, tag: str) -> str:
        """Remove namespace from XML tag."""
        return tag.split('}', 1)[-1] if '}' in tag else tag
    
    def _find_child_component(self, parent: ET.Element, tag_name: str) -> Optional[ET.Element]:
        """
        Find a child element with the given tag name (case-insensitive).
        
        Args:
            parent: Parent XML element.
            tag_name: Tag name to search for.
            
        Returns:
            Child element if found, None otherwise.
        """
        for child in parent:
            if self._clean_tag(child.tag).lower() == tag_name.lower():
                # Check for nil attribute
                if child.get('{http://www.w3.org/2001/XMLSchema-instance}nil') == 'true':
                    return None
                return child
        return None
    
    def _extract_text(self, xml_node: ET.Element) -> str:
        """
        Extract text content from an XML node.
        
        Args:
            xml_node: XML element to extract text from.
            
        Returns:
            Extracted text string.
        """
        # Try different text extraction methods
        text_methods = ['_text_str', 'Text']
        
        for method in text_methods:
            text_element = self._find_child_component(xml_node, method)
            if text_element is not None and text_element.text is not None:
                return text_element.text.strip()
        
        # Fallback to direct text content
        return (xml_node.text or '').strip()
    
    def _parse_node(self, xml_node: Optional[ET.Element]) -> Optional[ASTNode]:
        """
        Parse an XML node into an ASTNode.
        
        Args:
            xml_node: XML element to parse.
            
        Returns:
            Parsed ASTNode or None.
        """
        if xml_node is None:
            return None
        
        # Generate or get node ID
        node_id = xml_node.get('id', str(id(xml_node)))
        
        # Check cache to avoid infinite recursion
        if node_id in self.parsed_nodes:
            return self.parsed_nodes[node_id]
        
        # Determine node type
        component_type_attr = xml_node.get('{http://www.w3.org/2001/XMLSchema-instance}type')
        if component_type_attr:
            tag = component_type_attr.split(':')[-1]
        else:
            tag = self._clean_tag(xml_node.tag)
        
        # Extract text content
        text = self._extract_text(xml_node)
        
        if self.debug:
            logger.debug(f"Parsing node: {tag} with text: '{text}'")
        
        # Map node types to parser functions
        node_parsers = {
            'Oval': self._parse_oval_node,
            'Parallelogram': self._parse_parallelogram_node,
            'Rectangle': self._parse_assignment_node,
            'IF_Control': self._parse_if_node,
            'Loop': self._parse_loop_node,
            'Start': self._parse_oval_node,
        }
        
        # Get appropriate parser or use generic parser
        parser_func = node_parsers.get(tag, self._parse_generic_node)
        
        try:
            ast_node = parser_func(xml_node, tag, text)
            if ast_node is not None:
                ast_node.node_id = node_id
                self.parsed_nodes[node_id] = ast_node
            return ast_node
        except Exception as e:
            logger.error(f"Error parsing node {tag}: {e}")
            return None
    
    def _parse_oval_node(self, xml_node: ET.Element, tag: str, text: str) -> ASTNode:
        """Parse oval nodes (Start/End)."""
        node_type = 'Start' if 'start' in text.lower() else 'End'
        ast_node = ASTNode(node_type, text)
        
        successor = self._find_child_component(xml_node, '_Successor')
        ast_node.add_child(self._parse_node(successor))
        
        return ast_node
    
    def _parse_parallelogram_node(self, xml_node: ET.Element, tag: str, text: str) -> ASTNode:
        """Parse parallelogram nodes (Input/Output)."""
        is_input_elem = self._find_child_component(xml_node, '_is_input')
        is_input = is_input_elem is not None and is_input_elem.text == 'true'
        
        node_type = 'Input' if is_input else 'Output'
        
        if is_input:
            prompt_elem = self._find_child_component(xml_node, '_prompt')
            if prompt_elem is not None and prompt_elem.text:
                prompt_text = prompt_elem.text.strip('"')
                combined_text = f"{prompt_text} {text}" if prompt_text != text else text
                ast_node = ASTNode(node_type, combined_text, attributes={'variable': text, 'prompt': prompt_text})
            else:
                ast_node = ASTNode(node_type, text, attributes={'variable': text})
        else:
            ast_node = ASTNode(node_type, text)
        
        successor = self._find_child_component(xml_node, '_Successor')
        ast_node.add_child(self._parse_node(successor))
        
        return ast_node
    
    def _parse_assignment_node(self, xml_node: ET.Element, tag: str, text: str) -> ASTNode:
        """Parse rectangle nodes (Assignment)."""
        ast_node = ASTNode('Assignment', text)
        
        successor = self._find_child_component(xml_node, '_Successor')
        ast_node.add_child(self._parse_node(successor))
        
        return ast_node
    
    def _parse_if_node(self, xml_node: ET.Element, tag: str, text: str) -> ASTNode:
        """Parse IF control nodes."""
        ast_node = ASTNode('If', text)
        
        # Parse ELSE branch (right child)
        no_branch_node = self._find_child_component(xml_node, '_right_Child')
        else_node = self._parse_node(no_branch_node)
        if else_node is not None:
            else_node.attributes['branch'] = 'else'
            ast_node.add_child(else_node)
        
        # Parse THEN branch (left child)
        yes_branch_node = self._find_child_component(xml_node, '_left_Child')
        then_node = self._parse_node(yes_branch_node)
        if then_node is not None:
            then_node.attributes['branch'] = 'then'
            ast_node.add_child(then_node)
        
        # Parse successor (after if-else)
        successor = self._find_child_component(xml_node, '_Successor')
        ast_node.add_child(self._parse_node(successor))
        
        return ast_node
    
    def _parse_loop_node(self, xml_node: ET.Element, tag: str, text: str) -> ASTNode:
        """Parse loop nodes."""
        ast_node = ASTNode('Loop', text)
        
        # Parse loop body
        body_node = self._find_child_component(xml_node, '_after_Child')
        parsed_body = self._parse_node(body_node)
        if parsed_body is not None:
            parsed_body.attributes['loop_part'] = 'body'
            ast_node.add_child(parsed_body)
        
        # Parse exit condition
        exit_node = self._find_child_component(xml_node, '_Successor')
        parsed_exit = self._parse_node(exit_node)
        if parsed_exit is not None:
            ast_node.add_child(parsed_exit)
        
        return ast_node
    
    def _parse_generic_node(self, xml_node: ET.Element, tag: str, text: str) -> ASTNode:
        """Parse generic/unknown nodes."""
        ast_node = ASTNode(tag, text)
        
        successor = self._find_child_component(xml_node, '_Successor')
        ast_node.add_child(self._parse_node(successor))
        
        return ast_node


class RaptorAnalyzer:
    """
    Analyzer for RAPTOR ASTs that provides various analysis capabilities.
    """
    
    def __init__(self, ast_root: ASTNode):
        """
        Initialize the analyzer with an AST root.
        
        Args:
            ast_root: Root node of the AST to analyze.
        """
        self.ast_root = ast_root
    
    def get_all_variables(self) -> Set[str]:
        """Get all variables used in the flowchart."""
        return self.ast_root.get_all_variables()
    
    def get_node_count(self) -> Dict[str, int]:
        """Get count of each node type."""
        counts = {}
        self._count_nodes(self.ast_root, counts)
        return counts
    
    def _count_nodes(self, node: ASTNode, counts: Dict[str, int]) -> None:
        """Recursively count nodes by type."""
        counts[node.node_type] = counts.get(node.node_type, 0) + 1
        for child in node.children:
            self._count_nodes(child, counts)
    
    def find_nodes_by_type(self, node_type: str) -> List[ASTNode]:
        """Find all nodes of a specific type."""
        nodes = []
        self._find_nodes_by_type(self.ast_root, node_type, nodes)
        return nodes
    
    def _find_nodes_by_type(self, node: ASTNode, target_type: str, results: List[ASTNode]) -> None:
        """Recursively find nodes of a specific type."""
        if node.node_type == target_type:
            results.append(node)
        for child in node.children:
            self._find_nodes_by_type(child, target_type, results)
    
    def get_complexity_metrics(self) -> Dict[str, Any]:
        """Calculate complexity metrics for the flowchart."""
        node_counts = self.get_node_count()
        
        # Cyclomatic complexity approximation
        decision_nodes = node_counts.get('If', 0) + node_counts.get('Loop', 0)
        cyclomatic_complexity = decision_nodes + 1
        
        return {
            'total_nodes': sum(node_counts.values()),
            'decision_nodes': decision_nodes,
            'cyclomatic_complexity': cyclomatic_complexity,
            'variables_used': len(self.get_all_variables()),
            'node_breakdown': node_counts
        }


# Jupyter-friendly functions
def parse_raptor_file(filepath: Union[str, Path], debug: bool = False) -> Optional[ASTNode]:
    """
    Convenience function to parse a RAPTOR file.
    
    Args:
        filepath: Path to the RAPTOR file.
        debug: Enable debug output.
        
    Returns:
        AST root node or None if parsing fails.
    """
    try:
        parser = RaptorParser(debug=debug)
        return parser.parse_file(filepath)
    except RaptorParserError as e:
        print(f"Error: {e}")
        return None


def analyze_raptor_ast(ast_root: ASTNode) -> Dict[str, Any]:
    """
    Convenience function to analyze a RAPTOR AST.
    
    Args:
        ast_root: Root node of the AST.
        
    Returns:
        Analysis results dictionary.
    """
    analyzer = RaptorAnalyzer(ast_root)
    return analyzer.get_complexity_metrics()


def save_ast_to_json(ast_root: ASTNode, filepath: Union[str, Path]) -> None:
    """
    Save AST to JSON file.
    
    Args:
        ast_root: Root node of the AST.
        filepath: Output file path.
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(ast_root.to_dict(), f, indent=2)
    print(f"AST saved to {filepath}")


def load_ast_from_json(filepath: Union[str, Path]) -> Dict[str, Any]:
    """
    Load AST from JSON file.
    
    Args:
        filepath: Input file path.
        
    Returns:
        AST dictionary.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


# Example usage for Jupyter notebooks
def demo_usage():
    """Demonstrate how to use the parser in Jupyter."""
    print("RAPTOR Parser Demo")
    print("=" * 50)
    
    # Example of how to use the parser
    print("\n1. Basic Usage:")
    print("   ast = parse_raptor_file('your_file.rap')")
    print("   print(ast)")
    
    print("\n2. With Debug Output:")
    print("   ast = parse_raptor_file('your_file.rap', debug=True)")
    
    print("\n3. Analysis:")
    print("   metrics = analyze_raptor_ast(ast)")
    print("   print(metrics)")
    
    print("\n4. Save to JSON:")
    print("   save_ast_to_json(ast, 'output.json')")
    
    print("\n5. Manual Parser Usage:")
    print("   parser = RaptorParser(debug=True)")
    print("   ast = parser.parse_file('file.rap')")
    print("   stats = parser.get_statistics()")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python raptor_parser.py <input_file.rap>")
        print("\nFor interactive use, try: demo_usage()")
        demo_usage()
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    try:
        # Parse the file
        ast_root = parse_raptor_file(input_file, debug=True)
        
        if ast_root is None:
            print("Failed to parse the RAPTOR file.")
            sys.exit(1)
        
        # Save to JSON
        save_ast_to_json(ast_root, "output.json")
        
        # Show analysis
        metrics = analyze_raptor_ast(ast_root)
        print("\nAnalysis Results:")
        print(json.dumps(metrics, indent=2))
        
        print(f"\nAST Structure:")
        print(ast_root)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)