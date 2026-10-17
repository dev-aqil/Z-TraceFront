import networkx as nx
from sqlalchemy.orm import Session

from app.models import BatchRelationship


def build_batch_graph(db: Session) -> nx.DiGraph:
    """Directed graph: edge parent_batch -> child_batch (ingredient -> product)."""
    g = nx.DiGraph()
    for rel in db.query(BatchRelationship).all():
        g.add_edge(rel.parent_batch_id, rel.child_batch_id, quantity_used=rel.quantity_used)
    return g


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
