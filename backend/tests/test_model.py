"""Model-integrity and data-loading tests (Phase 0)."""

from celltwin.model.registry import (
    build_graph,
    list_cells,
    list_toxins,
    validate_cell,
)


def test_cells_and_toxins_present():
    assert "hepatocyte" in list_cells()
    for t in ["rotenone", "cyanide", "hydrogen_peroxide", "acetaminophen"]:
        assert t in list_toxins()


def test_cell_graph_is_valid(cell):
    assert validate_cell(cell) == []


def test_graph_builds(cell):
    g = build_graph(cell)
    assert g.number_of_nodes() == len(cell.nodes)
    assert g.number_of_edges() == len(cell.relations)


def test_process_map_targets_exist(cell):
    ids = {n.id for n in cell.nodes}
    for node_id, process in cell.process_map.items():
        assert node_id in ids
        assert process


def test_every_toxin_target_resolves(cell, toxins):
    ids = {n.id for n in cell.nodes}
    for toxin in toxins.values():
        assert toxin.targets, f"{toxin.id} has no targets"
        for tgt in toxin.targets:
            assert tgt.node in ids, f"{toxin.id} targets unknown node {tgt.node}"
            assert cell.resolve_process(tgt.node) is not None
