#
#    Copyright (C) 2018 by
#    Thomas Bonald <thomas.bonald@telecom-paristech.fr>
#    Bertrand Charpentier <bertrand.charpentier@live.fr>
#    All rights reserved.
#    BSD license.

#    source: https://github.com/tbonald/paris/blob/master/paris.py
#    theory: https://arxiv.org/pdf/1806.01664.pdf
#    this is a slighly modified version of paris, dubbed "krakow"


# @profile
def krakow(n_nodes, edges, alpha=2):
    """
    Hierarchical clustering using nearest-neighbor chain algorithm.

    alpha should be >= 1
    at alpha==1, the algorithm is the same as paris
    the higher the parameter, the more even the merges
    but too high values can harm clustering quality

    n_nodes: number of nodes (nodes are labeled 0 to n_nodes-1)
    edges: list of (u, v) tuples with integer node labels 0 to n_nodes-1
    alpha: balance parameter (beta is fixed at 1)
    """
    assert alpha >= 1

    n = n_nodes
    F = {node: {} for node in range(n)}
    w = [0.0] * (2 * n - 1)
    s = [1] * (2 * n - 1)
    for u_edge, v_edge in edges:
        if u_edge == v_edge:
            continue
        F[u_edge][v_edge] = 1
        F[v_edge][u_edge] = 1
        w[u_edge] += 1
        w[v_edge] += 1

    # connected components
    cc = []

    # dendrogram as list of merges
    D = []

    # cluster index
    u = n
    while n > 0:
        # nearest-neighbor chain
        chain = [next(iter(F))]
        while chain:
            a = chain.pop()
            F_a = F[a]
            w_a = w[a]
            # nearest neighbor
            dmin = float("inf")
            b = -1
            for v, edge_weight in F_a.items():
                w_v = w[v]
                if w_v < w_a:
                    small, big = w_v, w_a
                else:
                    small, big = w_a, w_v
                d = (small**alpha) * big / edge_weight
                if d < dmin:
                    b = v
                    dmin = d
                elif d == dmin and v < b:
                    b = v
            d = dmin
            if chain:
                c = chain.pop()
                if b == c:
                    # merge a,b
                    D.append([a, b, d, s[a] + s[b]])
                    # update graph: reuse a's adjacency dict for u
                    F_b = F[b]
                    # remove edge a-b from F_a (we'll reuse F_a as F[u])
                    del F_a[b]
                    # update neighbors of a to point to u instead of a
                    for v in F_a:
                        F_v = F[v]
                        F_v[u] = F_v.pop(a)
                    # merge b's neighbors into F_a (which becomes F[u])
                    del F_b[a]  # remove a from F_b before iterating
                    for v, edge_weight in F_b.items():
                        F_v = F[v]
                        del F_v[b]  # remove old b reference
                        if v in F_a:
                            F_a[v] += edge_weight
                            F_v[u] += edge_weight
                        else:
                            F_a[v] = edge_weight
                            F_v[u] = edge_weight
                    # assign a's dict to u and remove a and b
                    F[u] = F.pop(a)
                    del F[b]
                    n -= 1
                    # update weight and size
                    w[u] = w[a] + w[b]
                    s[u] = s[a] + s[b]
                    # change cluster index
                    u += 1
                else:
                    chain.append(c)
                    chain.append(a)
                    chain.append(b)
            elif b >= 0:
                chain.append(a)
                chain.append(b)
            else:
                # remove the connected component (isolated node)
                cc.append((a, s[a]))
                del F[a]
                n -= 1

    # add connected components to the dendrogram
    a, s = cc.pop()
    for b, t in cc:
        s += t
        D.append([a, b, float("inf"), s])
        a = u
        u += 1

    return D
