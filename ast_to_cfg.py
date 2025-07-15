#!/usr/bin/env python3
import json
import argparse
from graphviz import Digraph

class RaptorCFG:
    def __init__(self, ast):
        self.ast        = ast
        self.id_map     = {}
        self.type_map   = {}
        self.parent_map = {}
        self._build_maps(self.ast)

        self.g = Digraph(format='png')
        self.g.attr(
            rankdir='TB',
            splines='ortho',
            concentrate='false',
            nodesep='0.5',
            ranksep='0.75',
            center='true'
        )
        self.g.edge_attr.update(arrowhead='vee', color='#000')

    def _build_maps(self, node, parent=None):
        oid = node['node_id']
        if oid not in self.id_map:
            self.id_map[oid]   = f"n{len(self.id_map)+1}"
            self.type_map[oid] = node['node_type']
        if parent:
            self.parent_map[oid] = parent
        for c in node.get('children', []):
            self._build_maps(c, node)

    def _sanitize(self, txt):
        return (txt.replace('\n',' ')
                   .replace('"',"'")
                   .replace(':',' ')
                   .strip())

    def _find_last(self, node):
        if not node.get('children'):
            return node
        return self._find_last(node['children'][-1])

    def _next_sib(self, node):
        p = self.parent_map.get(node['node_id'])
        if not p:
            return None
        sibs = p.get('children', [])
        for i,s in enumerate(sibs):
            if s['node_id']==node['node_id']:
                return sibs[i+1] if i+1<len(sibs) else self._next_sib(p)
        return None

    def _render_node(self, node):
        oid   = node['node_id']
        mid   = self.id_map[oid]
        ntype = self.type_map[oid]
        text  = self._sanitize(node.get('text',''))

        shape = {
            'Start':'oval','End':'oval',
            'Input':'parallelogram','Output':'parallelogram',
            'Assignment':'rectangle','Declaration':'rectangle',
            'If':'diamond','Loop':'diamond'
        }[ntype]

        label = (
            f"if {text}?" if ntype=='If'
            else f"while {text}" if ntype=='Loop'
            else text or ntype
        )
        self.g.node(mid, label=label, shape=shape)

    def _render_edges(self, node, parent_oid=None):
        oid   = node['node_id']
        mid   = self.id_map[oid]
        ntype = self.type_map[oid]

        # Forward edge from parent → this
        if parent_oid and self.type_map[parent_oid] != 'End':
            pmid = self.id_map[parent_oid]
            branch = ''
            if self.type_map[parent_oid]=='If':
                for ch in self.parent_map[oid]['children']:
                    if ch['node_id']==oid:
                        br = ch['attributes'].get('branch','true')
                        branch = 'Yes' if br!='else' else 'No'
                        break
            elif self.type_map[parent_oid]=='Loop':
                for ch in self.parent_map[oid]['children']:
                    if ch['node_id']==oid:
                        lp = ch['attributes'].get('loop_part','body')
                        branch = 'Yes' if lp=='body' else ''
                        break
            self.g.edge(pmid, mid,
                        xlabel=branch, labelfontcolor='#000',
                        constraint='true')

        # Stop recursion at End
        if ntype=='End':
            return

        # Recurse children
        for child in node.get('children', []):
            self._render_node(child)
            self._render_edges(child, oid)

            # Loop‑back (non‑constraining)
            if self.type_map[oid]=='Loop':
                if child['attributes'].get('loop_part')=='body':
                    last = self._find_last(child)
                    lm   = self.id_map[last['node_id']]
                    self.g.edge(lm, mid, style='solid', constraint='false')

        # Loop‑exit (No)
        if ntype=='Loop':
            nxt = self._next_sib(node)
            if nxt:
                self.g.edge(mid, self.id_map[nxt['node_id']],
                            xlabel='No', labelfontcolor='#000',
                            constraint='true')

    def _rank_start_top(self):
        starts = [self.id_map[oid] for oid,t in self.type_map.items() if t=='Start']
        if not starts: return
        with self.g.subgraph() as sb:
            sb.attr(rank='min')
            for s in starts:
                sb.node(s)

    def _rank_end_bottom(self):
        ends = [self.id_map[oid] for oid,t in self.type_map.items() if t=='End']
        if not ends: return
        with self.g.subgraph() as sb:
            sb.attr(rank='max')
            # only End in this rank
            for e in ends:
                sb.node(e)

    def _align_start_end(self):
        starts = [self.id_map[oid] for oid,t in self.type_map.items() if t=='Start']
        ends   = [self.id_map[oid] for oid,t in self.type_map.items() if t=='End']
        if not starts or not ends: return
        # invisible constraining edge to center-align
        self.g.edge(starts[0], ends[0], style='invis', constraint='true')

    def render(self, out="output"):
        self._render_node(self.ast)
        self._render_edges(self.ast)
        # enforce Start at top, End at bottom, same column
        self._rank_start_top()
        self._rank_end_bottom()
        self._align_start_end()
        self.g.render(out, cleanup=True)
        print(f"✔ CFG written as {out}.png")

if __name__=="__main__":
    p = argparse.ArgumentParser()
    p.add_argument("json_file")
    p.add_argument("-o","--out", default="output")
    args = p.parse_args()

    ast = json.load(open(args.json_file))
    RaptorCFG(ast).render(out=args.out)
