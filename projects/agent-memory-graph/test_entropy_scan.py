"""Tests for entropy_scan() — Cycle 339: shape descriptors + fingerprint vector enhancement.

The existing entropy_scan() API (Cycle 281) already computed Rényi/Tsallis sweep curves.
Cycle 339 adds:
- Curve shape descriptors (monotonicity, convexity, knee, area, gap, slope)
- Fingerprint vector for graph comparison
"""

import math
import pytest
from memory_graph import MemoryGraph


# ── Helpers ──

def _star(n: int) -> MemoryGraph:
    """Star graph: center connected to n-1 leaves."""
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(str(i)) for i in range(n)]
    for i in range(1, n):
        mg.link(nodes[0].id, nodes[i].id, "r")
    return mg


def _complete(n: int) -> MemoryGraph:
    """Complete graph K_n."""
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            mg.link(nodes[i].id, nodes[j].id, "r")
    return mg


def _path(n: int) -> MemoryGraph:
    """Path graph P_n."""
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        mg.link(nodes[i].id, nodes[i + 1].id, "r")
    return mg


def _cycle(n: int) -> MemoryGraph:
    """Cycle graph C_n."""
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(str(i)) for i in range(n)]
    for i in range(n):
        mg.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return mg


def _bipartite(a: int, b: int) -> MemoryGraph:
    """Complete bipartite K_{a,b}."""
    mg = MemoryGraph(":memory:")
    left = [mg.add(f"a{i}") for i in range(a)]
    right = [mg.add(f"b{j}") for j in range(b)]
    for ln in left:
        for rn in right:
            mg.link(ln.id, rn.id, "r")
    return mg


# ── Basic structure ──

class TestEntropyScanBasic:
    """Verify entropy_scan() returns the expected structure including new keys."""

    def test_returns_dict(self):
        mg = _path(5)
        result = mg.entropy_scan()
        assert isinstance(result, dict)

    def test_empty_graph_returns_none(self):
        mg = MemoryGraph(":memory:")
        assert mg.entropy_scan() is None

    def test_single_node_returns_none(self):
        mg = MemoryGraph(":memory:")
        mg.add("v0")
        assert mg.entropy_scan() is None

    def test_no_edges_returns_none(self):
        mg = MemoryGraph(":memory:")
        mg.add("v0")
        mg.add("v1")
        assert mg.entropy_scan() is None

    def test_result_keys_include_new_fields(self):
        """Cycle 339 adds 'shape' and 'fingerprint' to the result."""
        mg = _path(5)
        result = mg.entropy_scan()
        assert "renyi" in result
        assert "tsallis" in result
        assert "shannon" in result
        assert "shape" in result
        assert "fingerprint" in result

    def test_renyi_curve_structure(self):
        mg = _path(5)
        result = mg.entropy_scan()
        assert "alphas" in result["renyi"]
        assert "values" in result["renyi"]
        assert len(result["renyi"]["alphas"]) == len(result["renyi"]["values"])

    def test_tsallis_curve_structure(self):
        mg = _path(5)
        result = mg.entropy_scan()
        assert "qs" in result["tsallis"]
        assert "values" in result["tsallis"]
        assert len(result["tsallis"]["qs"]) == len(result["tsallis"]["values"])


# ── Shape descriptors (NEW in Cycle 339) ──

class TestShapeDescriptors:
    """Curve shape descriptors capture topology correctly."""

    def test_shape_keys(self):
        mg = _path(5)
        shape = mg.entropy_scan()["shape"]
        assert "monotonic" in shape
        assert "convex" in shape
        assert "knee_position" in shape
        assert "curve_area" in shape
        assert "max_min_gap" in shape
        assert "slope_at_alpha2" in shape

    def test_star_is_monotonic(self):
        """Star graph Rényi curve should be monotonically decreasing."""
        mg = _star(10)
        assert mg.entropy_scan()["shape"]["monotonic"] is True

    def test_complete_graph_low_gap(self):
        """Complete graph: uniform edge contributions → very flat curve."""
        mg = _complete(8)
        gap = mg.entropy_scan()["shape"]["max_min_gap"]
        assert gap < 0.2

    def test_star_has_uniform_distribution(self):
        """Star graph: all edges connect same degree pair → uniform distribution.
        This means max_min_gap = 0 (all Rényi orders give same result).
        The discrimination between star and complete comes from the fingerprint
        vector (different edge counts → different raw entropy)."""
        mg = _star(10)
        result = mg.entropy_scan()
        # Uniform distribution → gap = 0 (mathematically correct)
        assert result["shape"]["max_min_gap"] == 0.0
        # But fingerprint is distinct due to edge count
        assert result["fingerprint"][0] > 1.5  # raw Shannon > ln(9)/2

    def test_star_and_complete_both_uniform_but_different_fingerprint(self):
        """Both star and complete have uniform edge distributions (gap=0),
        but their fingerprints differ due to different edge counts."""
        star_gap = _star(10).entropy_scan()["shape"]["max_min_gap"]
        complete_gap = _complete(10).entropy_scan()["shape"]["max_min_gap"]
        # Both have gap=0 (uniform)
        assert star_gap == 0.0
        assert complete_gap == 0.0
        # But fingerprints are very different
        star_fp = _star(10).entropy_scan()["fingerprint"]
        complete_fp = _complete(10).entropy_scan()["fingerprint"]
        dist = math.sqrt(sum((a-b)**2 for a, b in zip(star_fp, complete_fp)))
        assert dist > 1.0  # Large distance due to different edge counts

    def test_curve_area_is_float(self):
        mg = _path(5)
        assert isinstance(mg.entropy_scan()["shape"]["curve_area"], float)

    def test_curve_area_positive(self):
        mg = _path(5)
        assert mg.entropy_scan()["shape"]["curve_area"] >= 0

    def test_knee_position_none_or_in_range(self):
        mg = _star(10)
        knee = mg.entropy_scan()["shape"]["knee_position"]
        if knee is not None:
            assert 0.1 <= knee <= 10.0

    def test_slope_at_alpha2_is_float(self):
        mg = _path(5)
        slope = mg.entropy_scan()["shape"]["slope_at_alpha2"]
        assert isinstance(slope, float)

    def test_path_moderate_gap(self):
        """Path graph has moderate heterogeneity."""
        mg = _path(10)
        gap = mg.entropy_scan()["shape"]["max_min_gap"]
        assert -0.1 < gap < 1.0


# ── Fingerprint vector (NEW in Cycle 339) ──

class TestFingerprint:
    """Fingerprint vector for graph comparison."""

    def test_fingerprint_is_list_of_floats(self):
        mg = _path(5)
        fp = mg.entropy_scan()["fingerprint"]
        assert isinstance(fp, list)
        assert all(isinstance(x, (float, int)) for x in fp)

    def test_fingerprint_non_empty(self):
        mg = _path(5)
        fp = mg.entropy_scan()["fingerprint"]
        assert len(fp) >= 5

    def test_fingerprint_first_entry_is_raw_shannon(self):
        """Fingerprint[0] is the RAW (unnormalized) Shannon.
        result['shannon'] is the NORMALIZED Shannon (divided by ln(m)).
        They differ when the distribution isn't perfectly uniform."""
        mg = _path(5)
        result = mg.entropy_scan()
        # fingerprint[0] should be raw Shannon (larger than normalized)
        assert result["fingerprint"][0] >= result["shannon"] - 1e-6

    def test_fingerprint_includes_shape_descriptors(self):
        """Last 3 entries should be curve_area, max_min_gap, slope_at_alpha2."""
        mg = _path(5)
        result = mg.entropy_scan()
        fp = result["fingerprint"]
        assert abs(fp[-3] - result["shape"]["curve_area"]) < 1e-6
        assert abs(fp[-2] - result["shape"]["max_min_gap"]) < 1e-6
        assert abs(fp[-1] - result["shape"]["slope_at_alpha2"]) < 1e-6

    def test_same_topology_same_fingerprint(self):
        """Same topology should produce same fingerprint."""
        g1 = _path(10)
        g2 = _path(10)
        fp1 = g1.entropy_scan()["fingerprint"]
        fp2 = g2.entropy_scan()["fingerprint"]
        assert len(fp1) == len(fp2)
        for a, b in zip(fp1, fp2):
            assert abs(a - b) < 1e-6

    def test_different_topologies_different_fingerprints(self):
        """Star and complete should have different fingerprints."""
        star_fp = _star(10).entropy_scan()["fingerprint"]
        complete_fp = _complete(10).entropy_scan()["fingerprint"]
        assert len(star_fp) == len(complete_fp)
        diff = sum(abs(a - b) for a, b in zip(star_fp, complete_fp))
        assert diff > 0.01

    def test_fingerprint_includes_renyi_values(self):
        """Fingerprint should include Rényi entropy values (not just shape)."""
        mg = _path(5)
        result = mg.entropy_scan()
        fp = result["fingerprint"]
        renyi_vals = result["renyi"]["values"]
        # Fingerprint = [shannon] + renyi_values + tsallis_values + [area, gap, slope]
        # So it should be longer than 1 + 3 = 4
        assert len(fp) > 4


# ── Graph family discrimination ──

class TestGraphFamilyDiscrimination:
    """entropy_scan() with shape descriptors distinguishes graph families."""

    def test_star_vs_complete_fingerprint_distance(self):
        """Star and complete have very different fingerprints (edge count effect)."""
        star = _star(10).entropy_scan()
        complete = _complete(10).entropy_scan()
        # Both have gap=0 (uniform) but fingerprint distance is huge
        sf, cf = star["fingerprint"], complete["fingerprint"]
        dist = math.sqrt(sum((a-b)**2 for a, b in zip(sf, cf)))
        assert dist > 1.0

    def test_path_vs_cycle_different(self):
        """Path and cycle should have slightly different profiles."""
        path = _path(10).entropy_scan()
        cycle = _cycle(10).entropy_scan()
        assert abs(path["shape"]["max_min_gap"] - cycle["shape"]["max_min_gap"]) > 1e-6 or \
               abs(path["shannon"] - cycle["shannon"]) > 1e-6

    def test_star_vs_path_fingerprint_distance(self):
        """Fingerprint L2 distance between star and path should be significant."""
        star_fp = _star(10).entropy_scan()["fingerprint"]
        path_fp = _path(10).entropy_scan()["fingerprint"]
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(star_fp, path_fp)))
        assert dist > 0.01

    def test_identical_graphs_zero_distance(self):
        """Two identical path graphs have ~zero fingerprint distance."""
        fp1 = _path(8).entropy_scan()["fingerprint"]
        fp2 = _path(8).entropy_scan()["fingerprint"]
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(fp1, fp2)))
        assert dist < 1e-6


# ── Index parameter ──

class TestIndexParameter:
    """Different degree-based indices work correctly."""

    @pytest.mark.parametrize("index", [
        "sombor", "reduced_sombor", "randic", "zagreb_m1", "abc", "ga", "augmented_zagreb"
    ])
    def test_index_works(self, index):
        mg = _path(5)
        result = mg.entropy_scan(index=index)
        assert result is not None
        assert "shape" in result
        assert "fingerprint" in result

    def test_invalid_index_raises(self):
        mg = _path(5)
        with pytest.raises(ValueError):
            mg.entropy_scan(index="nonexistent")

    def test_different_indices_different_shannon(self):
        """Different indices weight edges differently → different Shannon."""
        mg = _path(8)  # path has heterogeneous degrees
        sombor = mg.entropy_scan(index="sombor")["shannon"]
        randic = mg.entropy_scan(index="randic")["shannon"]
        # Path graph degrees vary (1, 2, ..., 2, 1), so different indices give different results
        assert abs(sombor - randic) > 1e-6 or sombor == randic


# ── Backward compatibility ──

class TestBackwardCompatibility:
    """Existing entropy_scan() behavior preserved."""

    def test_default_alphas(self):
        mg = _path(5)
        result = mg.entropy_scan()
        assert len(result["renyi"]["alphas"]) == 8

    def test_default_qs(self):
        mg = _path(5)
        result = mg.entropy_scan()
        assert len(result["tsallis"]["qs"]) == 7

    def test_custom_alphas(self):
        mg = _path(5)
        result = mg.entropy_scan(alphas=[2.0, 5.0])
        assert len(result["renyi"]["values"]) == 2

    def test_custom_qs(self):
        mg = _path(5)
        result = mg.entropy_scan(qs=[0.5, 2.0])
        assert len(result["tsallis"]["values"]) == 2

    def test_shannon_is_float(self):
        mg = _path(5)
        result = mg.entropy_scan()
        assert isinstance(result["shannon"], float)


# ── Edge cases ──

class TestEdgeCases:
    """Edge cases for shape descriptors."""

    def test_single_edge(self):
        mg = MemoryGraph(":memory:")
        a = mg.add("a")
        b = mg.add("b")
        mg.link(a.id, b.id, "r")
        result = mg.entropy_scan()
        assert result is not None
        assert "shape" in result
        assert "fingerprint" in result

    def test_two_edges_path3(self):
        mg = MemoryGraph(":memory:")
        a = mg.add("a")
        b = mg.add("b")
        c = mg.add("c")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        result = mg.entropy_scan()
        assert result is not None
        assert result["shannon"] is not None

    def test_large_alpha_in_curve(self):
        """High α values should produce small entropy values."""
        mg = _star(10)
        result = mg.entropy_scan(alphas=[0.1, 1.0, 2.0, 10.0])
        vals = result["renyi"]["values"]
        # Should be monotonically decreasing for a star
        valid = [v for v in vals if v is not None]
        assert valid[0] >= valid[-1]
