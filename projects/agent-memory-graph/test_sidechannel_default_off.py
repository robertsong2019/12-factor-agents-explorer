#!/usr/bin/env python3
"""C545 production-decision pin: embedding side-channel stays OFF by default.

C545 full-census productionization attempt (the queue-head item deferred
since C543/C544): 48 hybrid form rows re-run end-to-end sc=False vs sc=True
(three-arm, HEAD judge on every arm):
  ledger stored 25/48 = scFalse-now 25/48 = scTrue-now 25/48, net-zero,
  exactly 1 pred changed (1903aded, still NEEDS_JUDGE), 0 noise rows
  (scFalse-now preds byte-identical to stored). The 29 embed rows are
  structurally banked-dead: pref_abstain gates them to the abstention
  answer before ranking can matter. #083's offline @5 recall gain does
  NOT transfer end-to-end. Verdict: keep sidechannel default False;
  these tests pin that decision so a default flip requires revisiting
  the C545 census (memory/2026-09-04-key-development-3.md).
"""
import inspect
import sys
import unittest

sys.path.insert(0, "/root/.openclaw/workspace/projects/agent-memory-graph")
import amg_bench_quality as Q


class TestSidechannelDefaultOff(unittest.TestCase):
    def test_sidechannel_flag_defaults_off(self):
        sig = inspect.signature(Q.LongMemEvalAdapter.__init__)
        self.assertEqual(sig.parameters["sidechannel"].default, False)

    def test_pref_abstain_defaults_on(self):
        # structural reason embed-mode rows can never bank: the pref
        # gate abstains before side-channel ranking can change anything
        sig = inspect.signature(Q.LongMemEvalAdapter.__init__)
        self.assertEqual(sig.parameters["pref_abstain"].default, True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
