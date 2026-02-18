use pyo3::prelude::*;
use std::collections::HashMap;

/// Hierarchical clustering using nearest-neighbor chain algorithm.
///
/// alpha should be >= 1
/// at alpha==1, the algorithm is the same as paris
/// the higher the parameter, the more even the merges
/// but too high values can harm clustering quality
///
/// n_nodes: number of nodes (nodes are labeled 0 to n_nodes-1)
/// edges: list of (u, v) tuples with integer node labels 0 to n_nodes-1
/// alpha: balance parameter (beta is fixed at 1)
///
/// Returns: dendrogram as list of [a, b, distance, size] merges
#[pyfunction]
#[pyo3(signature = (n_nodes, edges, alpha=2.0))]
fn krakow(n_nodes: usize, edges: Vec<(usize, usize)>, alpha: f64) -> PyResult<Vec<[f64; 4]>> {
    assert!(alpha >= 1.0, "alpha must be >= 1");

    let mut n = n_nodes;
    
    // F: adjacency dict - F[node] = {neighbor: edge_weight}
    let mut f: HashMap<usize, HashMap<usize, f64>> = HashMap::with_capacity(n);
    for node in 0..n {
        f.insert(node, HashMap::new());
    }
    
    // w: weighted degree, s: cluster size
    let mut w: Vec<f64> = vec![0.0; 2 * n - 1];
    let mut s: Vec<usize> = vec![1; 2 * n - 1];
    
    // Build adjacency structure from edges
    for (u_edge, v_edge) in edges {
        if u_edge == v_edge {
            continue;
        }
        f.get_mut(&u_edge).unwrap().insert(v_edge, 1.0);
        f.get_mut(&v_edge).unwrap().insert(u_edge, 1.0);
        w[u_edge] += 1.0;
        w[v_edge] += 1.0;
    }
    
    // connected components
    let mut cc: Vec<(usize, usize)> = Vec::new();
    
    // dendrogram as list of merges
    let mut d: Vec<[f64; 4]> = Vec::new();
    
    // cluster index
    let mut u = n_nodes;
    
    while n > 0 {
        // nearest-neighbor chain
        let first_key = *f.keys().next().unwrap();
        let mut chain: Vec<usize> = vec![first_key];
        
        while !chain.is_empty() {
            let a = chain.pop().unwrap();
            let f_a = f.get(&a).unwrap();
            let w_a = w[a];
            
            // nearest neighbor
            let mut dmin = f64::INFINITY;
            let mut b: Option<usize> = None;
            
            for (&v, &edge_weight) in f_a.iter() {
                let w_v = w[v];
                let (small, big) = if w_v < w_a { (w_v, w_a) } else { (w_a, w_v) };
                let dist = small.powf(alpha) * big / edge_weight;
                
                if dist < dmin || (dist == dmin && b.map_or(true, |curr_b| v < curr_b)) {
                    b = Some(v);
                    dmin = dist;
                }
            }
            
            if !chain.is_empty() {
                let c = chain.pop().unwrap();
                if b == Some(c) {
                    let b = b.unwrap();
                    // merge a, b
                    d.push([a as f64, b as f64, dmin, (s[a] + s[b]) as f64]);
                    
                    // update graph: we'll create new adjacency for u
                    let mut f_a = f.remove(&a).unwrap();
                    let f_b = f.remove(&b).unwrap();
                    
                    // remove edge a-b from f_a
                    f_a.remove(&b);
                    
                    // update neighbors of a to point to u instead of a
                    for &v in f_a.keys() {
                        let f_v = f.get_mut(&v).unwrap();
                        if let Some(weight) = f_v.remove(&a) {
                            f_v.insert(u, weight);
                        }
                    }
                    
                    // merge b's neighbors into f_a (which becomes f[u])
                    for (&v, &edge_weight) in f_b.iter() {
                        if v == a {
                            continue; // skip the a-b edge
                        }
                        let f_v = f.get_mut(&v).unwrap();
                        f_v.remove(&b); // remove old b reference
                        
                        if let Some(existing) = f_a.get_mut(&v) {
                            *existing += edge_weight;
                            *f_v.entry(u).or_insert(0.0) += edge_weight;
                        } else {
                            f_a.insert(v, edge_weight);
                            f_v.insert(u, edge_weight);
                        }
                    }
                    
                    // assign a's dict to u
                    f.insert(u, f_a);
                    n -= 1;
                    
                    // update weight and size
                    w[u] = w[a] + w[b];
                    s[u] = s[a] + s[b];
                    
                    // change cluster index
                    u += 1;
                } else {
                    chain.push(c);
                    chain.push(a);
                    chain.push(b.unwrap());
                }
            } else if let Some(b_val) = b {
                chain.push(a);
                chain.push(b_val);
            } else {
                // remove the connected component (isolated node)
                cc.push((a, s[a]));
                f.remove(&a);
                n -= 1;
            }
        }
    }
    
    // add connected components to the dendrogram
    if !cc.is_empty() {
        let (mut a, mut size) = cc.pop().unwrap();
        for (b, t) in cc {
            size += t;
            d.push([a as f64, b as f64, f64::INFINITY, size as f64]);
            a = u;
            u += 1;
        }
    }
    
    Ok(d)
}

/// A Python module implemented in Rust.
#[pymodule]
fn rust_krakow(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(krakow, m)?)?;
    Ok(())
}

