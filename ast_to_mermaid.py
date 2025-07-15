import json

def json_to_mermaid(json_data):
    def get_node_shape(node_type):
        return {
            'Start': '(({}))',           # Oval for Start
            'End': '(({}))',             # Oval for End
            'Input': '[[{}]]',           # Parallelogram for Input
            'Output': '[[{}]]',          # Parallelogram for Output
            'Assignment': '[{}]',        # Rectangle for Assignment
            'Declaration': '[{}]',       # Rectangle for Declaration
            'If': '{{ {} }}',            # Diamond for Decision
            'Loop': '{{ {} }}',          # Diamond for Loop
        }.get(node_type, '[{}]')         # Default Rectangle

    def sanitize_text(text):
        return (text.replace(':', ' ')
                    .replace('"', "'")
                    .replace('\n', ' ')
                    .replace('(', '')
                    .replace(')', '')
                    .strip())

    def create_node_id(original_id):
        if original_id not in id_mapping:
            id_mapping[original_id] = f"n{len(id_mapping) + 1}"
        return id_mapping[original_id]

    def render_node(node):
        nid = create_node_id(node['node_id'])
        shape = get_node_shape(node['node_type'])
        text = sanitize_text(node['text'])

        if node['node_type'] == 'Input':
            text = sanitize_text(node['attributes'].get('prompt', text))
        elif node['node_type'] == 'If':
            text = f"if {text}?"
        elif node['node_type'] == 'Loop':
            text = f"while {text}"

        nodes[nid] = f"{nid}{shape.format(text)}"
        return nid

    def walk(node, parent=None, label=None):
        current_id = render_node(node)

        if parent:
            if label:
                edges.append(f"{parent} -->|{label}| {current_id}")
            else:
                edges.append(f"{parent} --> {current_id}")

        children = node.get('children', [])

        for child in children:
            child_label = None
            if node['node_type'] == 'If':
                branch = child['attributes'].get('branch', 'true')
                child_label = 'Yes' if branch != 'else' else 'No'
            elif node['node_type'] == 'Loop':
                loop_part = child['attributes'].get('loop_part', 'body')
                child_label = 'Yes' if loop_part == 'body' else None

            walk(child, current_id, child_label)

            # Loop back from last node of loop body to loop condition
            if node['node_type'] == 'Loop' and child_label == 'Yes':
                last = find_last_node(child)
                if last:
                    edges.append(f"{last} --> {current_id}")

        # Add No edge from Loop node to next node after loop
        if node['node_type'] == 'Loop':
            next_id = find_exit_after_loop(node)
            if next_id:
                edges.append(f"{current_id} -->|No| {next_id}")

    def find_last_node(node):
        if not node.get('children'):
            return create_node_id(node['node_id'])
        return find_last_node(node['children'][-1])

    def find_exit_after_loop(loop_node):
        loop_id = loop_node['node_id']
        parent = parent_map.get(loop_id)
        if not parent:
            return None
        siblings = parent.get('children', [])
        for i, sibling in enumerate(siblings):
            if sibling['node_id'] == loop_id:
                if i + 1 < len(siblings):
                    return create_node_id(siblings[i + 1]['node_id'])
                else:
                    return find_next_node_after(parent)
        return None

    def find_next_node_after(node):
        p = parent_map.get(node['node_id'])
        if not p:
            return None
        siblings = p.get('children', [])
        for i, sibling in enumerate(siblings):
            if sibling['node_id'] == node['node_id']:
                if i + 1 < len(siblings):
                    return create_node_id(siblings[i + 1]['node_id'])
                else:
                    return find_next_node_after(p)
        return None

    def build_parent_map(node, parent=None):
        node_id = node['node_id']
        if parent and node_id not in parent_map:
            parent_map[node_id] = parent
        for child in node.get('children', []):
            build_parent_map(child, node)

    nodes = {}
    edges = []
    id_mapping = {}
    parent_map = {}

    build_parent_map(json_data)
    walk(json_data)

    lines = ["flowchart TD"]
    lines += [f"    {v}" for v in nodes.values()]
    lines += [f"    {e}" for e in edges]

    return "\n".join(lines)


if __name__ == "__main__":
    with open("output.json", "r") as f:
        json_input = json.load(f)

    mermaid_code = json_to_mermaid(json_input)
    print(mermaid_code)

    with open("flowchart.mmd", "w") as f:
        f.write(mermaid_code)
