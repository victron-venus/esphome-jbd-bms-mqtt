"""Exercise metadata job eligibility and concurrency with real caller expressions."""

import ast
import json
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CALLERS = (".github/workflows/auto-approve.yml", ".github/workflows/auto-merge.yml")


def definition(path: str):
    """Preserve GitHub's on key and expression scalars."""
    return yaml.load((ROOT / path).read_text(), Loader=yaml.BaseLoader)  # nosec B506: BaseLoader constructs primitive values only


def evaluate(expression: str, context: dict[str, object]):
    """Interpret the small expression subset used here; reject unknown syntax."""
    expression = expression.removeprefix("${{").removesuffix("}}")

    def value(match: re.Match[str]):
        values = [context]
        for field in match.group().split("."):
            values = (
                [item for value in values for item in value]
                if field == "*"
                else [v.get(field, "") if isinstance(v, dict) else "" for v in values]
            )
        return repr(values if ".*." in match.group() else values[0])

    expression = re.sub("\\b(?:github|inputs)(?:\\.[\\w*-]+)+", value, expression)
    expression = expression.replace("&&", " and ").replace("||", " or ")
    expression = re.sub("!(?!=)", " not ", expression)
    expression = re.sub("\\bnull\\b", "None", expression)

    def visit(node: ast.AST):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, (ast.Dict, ast.List)):
            return ast.literal_eval(node)
        if isinstance(node, ast.BoolOp):
            result = visit(node.values[0])
            for child in node.values[1:]:
                if isinstance(node.op, ast.And):
                    result = visit(child) if result else result
                else:
                    result = result if result else visit(child)
            return result
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not visit(node.operand)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, right = (visit(node.left), visit(node.comparators[0]))
            if isinstance(node.ops[0], ast.Eq):
                return left == right
            if isinstance(node.ops[0], ast.NotEq):
                return left != right
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            args = [visit(arg) for arg in node.args]
            if node.func.id == "fromJSON" and len(args) == 1:
                return json.loads(args[0])
            if node.func.id == "contains" and len(args) == 2:
                return args[1] in args[0]
        message = f"Unsupported metadata expression: {expression}"
        raise AssertionError(message)

    return visit(ast.parse("(" + expression.strip() + ")", mode="eval").body)


def context(
    action: str = "opened",
    changes: dict[str, object] | None = None,
    run: str = "10",
    event: str = "pull_request_target",
):
    """Use the official edited schema: changes.base contains ref/sha from values."""
    return {
        "github": {
            "workflow": "metadata",
            "repository": "example/repo",
            "run_id": run,
            "event_name": event,
            "event": {
                "action": action,
                "changes": changes or {},
                "pull_request": {
                    "number": 42,
                    "user": {"login": "4alvit"},
                    "draft": False,
                    "head": {"repo": {"full_name": "contributor/fork"}},
                    "labels": [{"name": "automerge"}],
                },
            },
        },
        "inputs": {"authors": '["4alvit","dependabot[bot]"]'},
    }


def group(workflow: dict[str, object], data: dict[str, object]):
    """Render each interpolation to compare actual workflow concurrency groups."""
    return re.sub(
        "\\$\\{\\{.*?\\}\\}",
        lambda match: str(evaluate(match.group(), data)),
        workflow["concurrency"]["group"],
    )


class MetadataEventsTests(unittest.TestCase):
    """Skip metadata churn without losing retargeting or cancellation guarantees."""

    def test_body_title_edits_never_allocate_metadata_jobs(self):
        for name in CALLERS:
            job = next(iter(definition(name)["jobs"].values()))
            for changes in (
                {},
                {"body": {"from": ""}},
                {"title": {"from": "old"}},
                {"body": {"from": "old"}, "title": {"from": "old"}},
            ):
                with self.subTest(workflow=name, changes=changes):
                    assert not evaluate(job["if"], context("edited", changes))

    def test_retarget_and_other_state_events_remain_eligible(self):
        base = {"base": {"ref": {"from": "old"}, "sha": {"from": "a" * 40}}}
        for name in CALLERS:
            job = next(iter(definition(name)["jobs"].values()))
            for action, changes in (
                ("edited", base),
                ("edited", base | {"body": {"from": "old"}}),
                ("opened", {}),
                ("synchronize", {}),
                ("reopened", {}),
                ("ready_for_review", {}),
                ("labeled", {}),
                ("unlabeled", {}),
            ):
                with self.subTest(workflow=name, action=action):
                    assert evaluate(job["if"], context(action, changes))

    def test_ignored_edits_cannot_cancel_or_replace_meaningful_runs(self):
        for name in CALLERS:
            workflow = definition(name)
            with self.subTest(workflow=name):
                active = group(workflow, context("labeled"))
                pending = group(workflow, context("synchronize", run="11"))
                ignored = group(workflow, context("edited", run="12"))
                next_ignored = group(workflow, context("edited", run="13"))
                retargeted = group(
                    workflow, context("edited", {"base": {"ref": {"from": "other"}}})
                )
                assert active == pending
                assert active == retargeted
                assert ignored not in (active, pending)
                assert ignored != next_ignored
                assert workflow["concurrency"]["cancel-in-progress"] == "true"
                for trigger in workflow["on"].values():
                    assert "edited" in trigger["types"]
                    assert "converted_to_draft" in trigger["types"]

    def test_trust_draft_and_dependabot_routing_are_preserved(self):
        workflow = definition(CALLERS[0])
        condition = workflow["jobs"]["auto-approve"]["if"]
        for author, draft, event, same_repo, expected in (
            ("stranger", False, "pull_request", True, False),
            ("4alvit", True, "pull_request", True, False),
            ("4alvit", False, "pull_request", True, True),
            ("4alvit", False, "pull_request_target", True, False),
            ("4alvit", False, "pull_request_target", False, True),
            ("dependabot[bot]", False, "pull_request", True, True),
            ("dependabot[bot]", False, "pull_request_target", True, False),
        ):
            data = context(event=event)
            pr = data["github"]["event"]["pull_request"]
            pr["user"]["login"] = author
            pr["draft"] = draft
            if same_repo:
                pr["head"]["repo"]["full_name"] = data["github"]["repository"]
            with self.subTest(
                author=author, draft=draft, event=event, same_repo=same_repo
            ):
                assert bool(evaluate(condition, data)) == expected


if __name__ == "__main__":
    unittest.main()
