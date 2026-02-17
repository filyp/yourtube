def from_category(G, ids, categories):
    # note: if some of the ids hasn't beed scraped, they will be filtered out
    # regardless of their category (because it isn't known)
    for id_ in ids:
        node = G.nodes[id_]
        if node.get("category") in categories:
            yield id_


def not_down(G, ids):
    for id_ in ids:
        node = G.nodes[id_]
        if not node.get("is_down"):
            yield id_


def get_neighborhood(G, ids):
    out_edges = G.out_edges(ids)
    return G.edge_subgraph(out_edges).nodes


def select_nodes_to_cluster(G):
    sources = list(G.nodes)
    sources = not_down(G, sources)
    return list(get_neighborhood(G, sources))
