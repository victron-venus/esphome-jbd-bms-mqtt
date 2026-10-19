"""The Linux-only compiler accepts its ARC pool without admitting fork jobs."""

import itertools
import json
import unittest

from test_metadata_events import definition, evaluate


class CompilerRunnerTests(unittest.TestCase):
    def test_modes_events_and_linux_targets(self):
        expression = definition(".github/workflows/ci.yml")["jobs"]["validate"]["runs-on"]
        events = (
            ("pull_request", "refs/pull/1/merge", "example/repo", True),
            ("pull_request", "refs/pull/1/merge", "external/fork", False),
            ("pull_request_target", "refs/heads/main", "example/repo", False),
            ("push", "refs/heads/main", "example/repo", True),
            ("push", "refs/heads/topic", "example/repo", False),
            ("push", "refs/tags/v1.0", "example/repo", False),
            ("schedule", "refs/heads/main", "example/repo", True),
            ("workflow_dispatch", "refs/heads/main", "example/repo", True),
            ("workflow_dispatch", "refs/heads/topic", "example/repo", False),
        )
        targets = (
            ([], False),
            (["self-hosted", "Linux", "X64"], True),
            (["victron-reserve-ci-x64"], True),
            (["victron-reserve-automation-x64"], False),
            (["victron-reserve-release-x64"], False),
            (["self-hosted", "macOS", "ARM64"], False),
            (["unknown-pool"], False),
        )
        for mode, event_row, target_row in itertools.product(
            ("", "github", "self-hosted", "k3s"), events, targets
        ):
            event, ref, source, trusted = event_row
            labels, linux = target_row
            data = {
                "vars": {"CI_RUNNER_MODE": mode, "CI_RUNNER_LABELS": json.dumps(labels)},
                "github": {
                    "repository": "example/repo",
                    "event_name": event,
                    "ref": ref,
                    "event": {
                        "repository": {"default_branch": "main"},
                        "pull_request": {"head": {"repo": {"full_name": source}}},
                    },
                },
            }
            expected = labels if mode in ("self-hosted", "k3s") and trusted and linux else ["ubuntu-latest"]
            with self.subTest(mode=mode, event=event, ref=ref, labels=labels):
                self.assertEqual(evaluate(expression, data), expected)


if __name__ == "__main__":
    unittest.main()
