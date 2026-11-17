import networkx as nx
from sqlalchemy.orm import Session

from app.models import BatchRelationship


def build_batch_graph(db: Session) -> nx.DiGraph:
    """Directed graph: edge parent_batch -> child_batch (ingredient -> product)."""
    g = nx.DiGraph()
    for rel in db.query(BatchRelationship).all():
        g.add_edge(rel.parent_batch_id, rel.child_batch_id, quantity_used=rel.quantity_used)
    return g


def creates_cycle(g: nx.DiGraph, parent: int, child: int) -> bool:
    """Would the ingredient link parent -> child make a lot one of its own ingredients?"""
    return parent == child or (parent in g and child in g and nx.has_path(g, child, parent))


def trace_backward(db: Session, batch_id: int) -> list[int]:
    """Ancestors of batch_id: where did it come from."""
    g = build_batch_graph(db)
    if batch_id not in g:
        return []
    return list(nx.ancestors(g, batch_id))


def trace_forward(db: Session, batch_id: int) -> list[int]:
    """Descendants of batch_id: where else could it have gone."""
    g = build_batch_graph(db)
    if batch_id not in g:
        return []
    return list(nx.descendants(g, batch_id))
