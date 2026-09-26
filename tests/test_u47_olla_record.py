"""U47-O2: a local-model run row names its model and work, so the ledger can be joined to pilot outcomes."""

import unittest

from v7_harness.adapters.ollama_worker import contract_work_id


class OllaRecordTest(unittest.TestCase):
    def test_work_id_is_read_from_the_contract(self):
        prompt = "# Manual\n\n```contract\nwork_id: U47-X1\nworker: ollama\n```\nDo it."
        self.assertEqual("U47-X1", contract_work_id(prompt))

    def test_no_contract_gives_none(self):
        self.assertIsNone(contract_work_id("just a task"))


if __name__ == "__main__":
    unittest.main()
