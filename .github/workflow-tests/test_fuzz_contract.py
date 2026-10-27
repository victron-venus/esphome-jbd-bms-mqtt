"""Keep the callable candidate workflow and its checked-out runner in sync."""

from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]


class FuzzContractTests(unittest.TestCase):
    def test_candidate_workflow_and_runner_share_an_immutable_revision(self):
        workflow = yaml.load(
            (ROOT / ".github/workflows/fuzz-candidate.yml").read_text(),
            Loader=yaml.BaseLoader,
        )
        job = workflow["jobs"]["fuzz"]
        workflow_revision = job["uses"].rsplit("@", 1)[1]
        self.assertRegex(workflow_revision, r"^[0-9a-f]{40}$")
        self.assertEqual(workflow_revision, job["with"]["toolkit-ref"])


if __name__ == "__main__":
    unittest.main()
