"""Local-first issue/Project synchronization. Preview unless --apply is explicit."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ("Purpose", "Tasks", "Acceptance criteria", "Completion evidence", "Completion log")
ISSUE_FIELDS = "id number title body state stateReason url updatedAt"
ITEM_FIELDS = """
id isArchived project { id } content { ... on Issue { id } }
fieldValueByName(name:"Status") {
  ... on ProjectV2ItemFieldSingleSelectValue { optionId }
}
"""
STATUS_MAP = {
    "NOT_STARTED": ("OPEN", None, "Backlog"),
    "DEFERRED": ("OPEN", None, "Backlog"),
    "READY": ("OPEN", None, "Ready"),
    "IN_PROGRESS": ("OPEN", None, "In progress"),
    "IN_REVIEW": ("OPEN", None, "In review"),
    "DONE": ("CLOSED", "COMPLETED", "Done"),
    "CANCELLED": ("CLOSED", "NOT_PLANNED", "Backlog"),
    "SUPERSEDED": ("CLOSED", "NOT_PLANNED", "Backlog"),
}
PRIVATE_PATH = re.compile(
    r"(?i)(?:\.agent-context(?:[/\\]|\b)|(?:^|[/\\])\.env(?:[./\\\s)]|$)"
    r"|configs[/\\](?:config|answers|searches|question_bank)\.yaml"
    r"|(?:generated|logs|screenshots|exports|\.browser-profile)[/\\])"
)


class SyncError(Exception):
    """A blocked operation; successful partial progress must be retained."""


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_atomic(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as target:
            temporary = Path(target.name)
            target.write(text)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def save_json(path: Path, value):
    text = json.dumps(value, indent=2, ensure_ascii=True) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        write_atomic(path, text)


@contextmanager
def writer_lock(root: Path):
    path = root / ".todo-sync.lock"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise SyncError("Writer lock exists; inspect its PID before manual recovery.") from error
    try:
        with os.fdopen(descriptor, "w") as target:
            target.write(str(os.getpid()))
        yield
    finally:
        path.unlink()


class GitHub:
    def request(self, query: str, **variables):
        mutation = query.lstrip().startswith("mutation")
        environment = os.environ.copy()
        environment.pop("GH_DEBUG", None)
        for attempt in range(3):
            try:
                result = subprocess.run(
                    ["gh", "api", "--hostname", "github.com", "graphql", "--input", "-"],
                    input=json.dumps({"query": query, "variables": variables}),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=120,
                    env=environment,
                )
            except subprocess.TimeoutExpired as error:
                if mutation or attempt == 2:
                    raise SyncError(
                        "GitHub timeout; mutation outcome may be uncertain. Reconcile before retry."
                    ) from error
                time.sleep(attempt + 1)
                continue
            if result.returncode:
                message = result.stderr.strip()
                for key in ("GH_TOKEN", "TODO_SYNC_GITHUB_TOKEN", "GITHUB_TOKEN"):
                    if environment.get(key):
                        message = message.replace(environment[key], "[redacted]")
                transient = any(
                    word in message.lower()
                    for word in ("timeout", "timed out", "502", "503", "rate limit", "connection")
                )
                if not mutation and transient and attempt < 2:
                    time.sleep(attempt + 1)
                    continue
                raise SyncError("GitHub request failed: " + message[:800])
            value = json.loads(result.stdout)
            if value.get("errors") or value.get("data") is None:
                raise SyncError("GraphQL errors/missing data; no empty inventory assumed.")
            return value["data"]
        raise SyncError("GitHub read retries exhausted.")

    def connection(self, query: str, route: tuple, **variables):
        nodes, cursor, seen = [], None, set()
        while True:
            value = self.request(query, cursor=cursor, **variables)
            for key in route:
                if value is None:
                    raise SyncError("Missing or inaccessible GitHub connection.")
                value = value[key]
            if value is None or any(node is None for node in value["nodes"]):
                raise SyncError("Missing/inaccessible connection or node.")
            nodes.extend(value["nodes"])
            page = value["pageInfo"]
            if not page["hasNextPage"]:
                return nodes
            cursor = page["endCursor"]
            if not cursor or cursor in seen:
                raise SyncError("Invalid GitHub pagination cursor.")
            seen.add(cursor)

    def inventory(self, config):
        owner, name = config["repository"].split("/")
        metadata = self.request(
            """
query($owner:String!,$name:String!,$project:ID!) {
 viewer { login }
 repository(owner:$owner,name:$name) { id nameWithOwner isPrivate viewerPermission }
 node(id:$project) { ... on ProjectV2 {
   id title url public closed viewerCanUpdate
   owner { ... on User { login } ... on Organization { login } }
   repositories(first:100) { nodes { id } pageInfo { hasNextPage } }
   fields(first:100) { nodes {
     ... on ProjectV2SingleSelectField { id name options { id name } }
   } pageInfo { hasNextPage } }
 } }
}""",
            owner=owner,
            name=name,
            project=config["project"]["id"],
        )
        repo, project = metadata["repository"], metadata["node"]
        if metadata["viewer"]["login"] != config["account"]:
            raise SyncError("Unexpected authenticated account; no fallback account is adopted.")
        if not repo or repo["id"] != config["repository_id"]:
            raise SyncError("Repository identity changed or is inaccessible.")
        if repo["nameWithOwner"] != config["repository"] or repo["isPrivate"] != config["private"]:
            raise SyncError("Repository rename/visibility needs reviewed configuration.")
        if (
            not project
            or project["public"] != config["project"]["public"]
            or project["owner"]["login"] != owner
            or project["closed"]
        ):
            raise SyncError("Project identity/owner/visibility/closed state needs review.")
        if not project["viewerCanUpdate"] or repo["viewerPermission"] not in (
            "WRITE",
            "MAINTAIN",
            "ADMIN",
        ):
            raise SyncError("Issue/Project write permission unavailable.")
        if (
            project["fields"]["pageInfo"]["hasNextPage"]
            or project["repositories"]["pageInfo"]["hasNextPage"]
        ):
            raise SyncError(
                "Project metadata exceeds bounded read; extend inventory before writes."
            )
        if config["repository_id"] not in [node["id"] for node in project["repositories"]["nodes"]]:
            raise SyncError("Configured Project is no longer linked to the repository.")
        status = [
            field
            for field in project["fields"]["nodes"]
            if field.get("id") == config["project"]["status_field_id"]
        ]
        if len(status) != 1 or status[0]["name"] != "Status":
            raise SyncError("Configured Status field missing or renamed.")
        options = {option["id"]: option["name"] for option in status[0]["options"]}
        for stage, identifier in config["project"]["options"].items():
            if options.get(identifier) != config["project"]["option_names"][stage]:
                raise SyncError("Status option changed: " + stage)
        issues = self.connection(
            """
query($owner:String!,$name:String!,$cursor:String) {
 repository(owner:$owner,name:$name) {
   issues(first:100,after:$cursor,states:[OPEN,CLOSED]) {
     nodes { """
            + ISSUE_FIELDS
            + """ } pageInfo { hasNextPage endCursor }
   }
 }
}""",
            ("repository", "issues"),
            owner=owner,
            name=name,
        )
        items = self.connection(
            """
query($project:ID!,$cursor:String) { node(id:$project) { ... on ProjectV2 {
 items(first:100,after:$cursor) { nodes { """
            + ITEM_FIELDS
            + """ } pageInfo { hasNextPage endCursor } }
} } }""",
            ("node", "items"),
            project=project["id"],
        )
        return metadata["viewer"]["login"], issues, items

    def issue(self, identifier: str):
        value = self.request(
            "query($id:ID!) { node(id:$id) { ... on Issue { " + ISSUE_FIELDS + " } } }",
            id=identifier,
        )["node"]
        if not value:
            raise SyncError("Mapped issue disappeared or became inaccessible.")
        return value

    def item(self, identifier: str):
        value = self.request(
            "query($id:ID!) { node(id:$id) { ... on ProjectV2Item { " + ITEM_FIELDS + " } } }",
            id=identifier,
        )["node"]
        if not value:
            raise SyncError("Mapped Project item disappeared or became inaccessible.")
        return value

    def create_issue(self, repository: str, title: str, body: str):
        return self.request(
            """
mutation($repo:ID!,$title:String!,$body:String!) {
 createIssue(input:{repositoryId:$repo,title:$title,body:$body}) { issue {
""" + ISSUE_FIELDS + """ } } }""",
            repo=repository,
            title=title,
            body=body,
        )["createIssue"]["issue"]

    def update_issue(self, issue: str, title: str, body: str):
        self.request(
            """mutation($id:ID!,$title:String!,$body:String!) {
 updateIssue(input:{id:$id,title:$title,body:$body}) { issue { id } }
}""",
            id=issue,
            title=title,
            body=body,
        )

    def lifecycle(self, issue: str, state: str, reason):
        self.request(
            """mutation($id:ID!,$state:IssueState!,$reason:IssueClosedStateReason) {
 updateIssue(input:{id:$id,stateInput:{value:$state,stateReason:$reason}}) { issue { id } }
}""",
            id=issue,
            state=state,
            reason=reason,
        )

    def add_item(self, project: str, issue: str):
        return self.request(
            """mutation($project:ID!,$issue:ID!) {
 addProjectV2ItemById(input:{projectId:$project,contentId:$issue}) { item { id } }
}""",
            project=project,
            issue=issue,
        )["addProjectV2ItemById"]["item"]["id"]

    def set_status(self, project: str, item: str, field: str, option: str):
        self.request(
            """mutation($project:ID!,$item:ID!,$field:ID!,$option:String!) {
 updateProjectV2ItemFieldValue(input:{
 projectId:$project,itemId:$item,fieldId:$field,value:{singleSelectOptionId:$option}
 }) { projectV2Item { id } }
}""",
            project=project,
            item=item,
            field=field,
            option=option,
        )


def markers(identifier: str):
    return (f"<!-- lea-todo:{identifier}:begin -->", f"<!-- lea-todo:{identifier}:end -->")


def managed_section(body: str, identifier: str) -> str:
    begin, end = markers(identifier)
    if body.count(begin) != 1 or body.count(end) != 1 or body.index(end) < body.index(begin):
        raise SyncError("Managed issue markers missing, duplicated or out of order.")
    return body[body.index(begin) : body.index(end) + len(end)]


def field(text: str, name: str, optional=False):
    matches = re.findall(rf"^{re.escape(name)}:[ \t]*(.*)$", text, re.M)
    if not matches and optional:
        return None
    if len(matches) != 1 or not matches[0].strip():
        raise SyncError("Expected one nonempty field: " + name)
    return matches[0].strip()


def section(text: str, name: str) -> str:
    matches = list(re.finditer(rf"^## {re.escape(name)}[ \t]*$", text, re.M))
    if len(matches) != 1:
        raise SyncError("Expected one section: " + name)
    return re.split(r"^## ", text[matches[0].end() :], maxsplit=1, flags=re.M)[0].strip()


def guard_public(text: str):
    if re.search(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})", text):
        raise SyncError("Token-shaped content blocked; review without publishing it.")
    if re.search(r"(?i)\b(?:[A-Z_]*(?:TOKEN|PASSWORD|SECRET|API_KEY))\s*[:=]\s*\S+", text):
        raise SyncError("Credential-shaped assignment blocked.")
    if re.search(r"\b[A-Za-z]:[\\/]|\\\\[A-Za-z0-9]", text) or PRIVATE_PATH.search(text):
        raise SyncError(
            "Private/local path blocked; an explicitly reviewed projection is required."
        )
    for email in re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text):
        if not email.lower().endswith(("@example.com", "@example.org", "@example.net")):
            raise SyncError("Non-fixture contact address blocked.")


def public_projection(text: str, path: Path, config, root: Path) -> str:
    guard_public(text)

    def link(match):
        target = match[1]
        parsed = urlsplit(target)
        if parsed.scheme:
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.hostname in ("localhost", "127.0.0.1")
            ):
                raise SyncError("Only credential-free public HTTPS links may be projected.")
            return match[0]
        if target.startswith("#"):
            return match[0]
        relative, separator, fragment = target.partition("#")
        destination = (path.parent / relative).resolve()
        if not destination.is_relative_to(root.resolve()):
            raise SyncError("Relative public link escapes the repository.")
        relative = destination.relative_to(root.resolve()).as_posix()
        guard_public(relative)
        source = f"https://github.com/{config['repository']}/blob/{config['branch']}/"
        return "](" + source + quote(relative) + separator + fragment + ")"

    return re.sub(r"\]\(([^)\s]+)\)", link, text)


def parse_workstream(path: Path, identifier: str, config, root: Path):
    if not path.resolve().is_relative_to((root / config["todo_dir"]).resolve()):
        raise SyncError("Workstream path escapes the configured TODO directory.")
    text = path.read_text(encoding="utf-8")
    stable = field(text, "Workstream-ID", optional=True)
    if stable and stable != identifier:
        raise SyncError("Local stable identity mismatch.")
    if field(text, "Publication") != "PUBLIC_SAFE_PROJECTION":
        raise SyncError("Explicit public-safe projection approval is required.")
    clean = re.sub(r"^(Workstream-ID|GitHub-Issue|Source-record):[^\n]*\n", "", text, flags=re.M)
    for name in ("Status", "Milestone", "Dependencies"):
        field(clean, name)
    contents = {name: section(clean, name) for name in SECTIONS}
    if any(not value for value in contents.values()):
        raise SyncError("Empty workstream section.")
    status = field(clean, "Status")
    if status == "BLOCKED":
        stage = field(clean, "Blocked-stage")
        field(clean, "Blocker")
        if stage not in ("Backlog", "Ready", "In progress", "In review"):
            raise SyncError("Blocked-stage must preserve an explicit non-complete stage.")
        state, reason = "OPEN", None
    elif status in STATUS_MAP:
        state, reason, stage = STATUS_MAP[status]
    else:
        raise SyncError("Unreviewed exact Status value; no substring classification.")
    if status == "DONE" and (
        contents["Completion evidence"] == "Not completed."
        or re.search(r"^- \[ \]", contents["Tasks"] + "\n" + contents["Acceptance criteria"], re.M)
    ):
        raise SyncError("DONE needs evidence and no outstanding in-scope tasks/acceptance.")
    title_match = re.match(r"# ([^\n]+)\n", clean)
    if not title_match:
        raise SyncError("Expected one leading workstream title.")
    guard_public(title_match[1])
    begin, end = markers(identifier)
    relative = path.relative_to(root).as_posix()
    source = f"https://github.com/{config['repository']}/blob/{config['branch']}/{quote(relative)}"
    body = "\n\n".join(
        (
            begin,
            f"Source workstream: [{relative}]({source})",
            "Reviewed public-safe projection, not a verbatim copy of legacy applicant records. "
            "Local TODO owns this managed section; tracking metadata and local provenance are omitted. "
            "Historical dates describe attributed evidence, not backdated GitHub activity. "
            "Source links can lag uncommitted changes. Tests are not human approval or publication.",
            public_projection(clean.strip(), path, config, root),
            end,
        )
    )
    if len(body) > 60000:
        raise SyncError("Managed body exceeds safe GitHub size.")
    return {
        "title": f"[{identifier}] {title_match[1]}",
        "body": body,
        "managed": digest(body),
        "lifecycle": [state, reason],
        "status": config["project"]["options"][stage],
        "stage": stage,
    }


def snapshot(issue, item, identifier: str):
    return {
        "title": issue["title"],
        "managed": digest(managed_section(issue["body"] or "", identifier)),
        "lifecycle": [
            issue["state"],
            issue["stateReason"] if issue["state"] == "CLOSED" else None,
        ],
        "status": (
            item["fieldValueByName"]["optionId"] if item and item["fieldValueByName"] else None
        ),
    }


def desired_snapshot(work):
    return {key: work[key] for key in ("title", "managed", "lifecycle", "status")}


def check_conflicts(current, record):
    baseline = record.get("baseline")
    if baseline is None:
        raise SyncError("No verified baseline; explicit reconciliation required.")
    for key, value in current.items():
        allowed = [baseline[key]]
        for pending in ("pending", "pending_origin"):
            if key in record.get(pending, {}):
                allowed.append(record[pending][key])
        if value not in allowed:
            raise SyncError("Remote human edit conflicts with managed " + key + ".")


def equivalent_issue_url(actual: str, expected: str, config) -> bool:
    def identity(url):
        parsed = urlsplit(url)
        match = re.fullmatch(r"/([^/]+/[^/]+)/issues/([1-9]\d*)", parsed.path)
        allowed = [config["repository"], *config.get("repository_aliases", [])]
        if (
            parsed.scheme != "https"
            or parsed.netloc != "github.com"
            or parsed.query
            or parsed.fragment
            or not match
            or match[1].casefold() not in {name.casefold() for name in allowed}
        ):
            return None
        return match[2]

    return identity(actual) is not None and identity(actual) == identity(expected)


def write_backlink(path: Path, identifier: str, url: str, config):
    text = path.read_text(encoding="utf-8")
    stable, actual = field(text, "Workstream-ID", True), field(text, "GitHub-Issue", True)
    if stable not in (None, identifier) or (
        actual is not None and not equivalent_issue_url(actual, url, config)
    ):
        raise SyncError("Conflicting local identity/backlink.")
    clean = re.sub(r"^(Workstream-ID|GitHub-Issue):[^\n]*\n", "", text, flags=re.M)
    first, rest = clean.split("\n", 1)
    updated = first + f"\nWorkstream-ID: {identifier}\nGitHub-Issue: {url}\n" + rest
    if updated != text:
        write_atomic(path, updated)


def find_issue(issues, identifier: str, record):
    begin, _ = markers(identifier)
    matches = [issue for issue in issues if begin in (issue["body"] or "")]
    if len(matches) > 1:
        raise SyncError("Duplicate stable issue identity; reconcile without deleting.")
    if record.get("issue_id"):
        if len(matches) != 1 or matches[0]["id"] != record["issue_id"]:
            raise SyncError("Mapped issue/marker disappeared or changed; no replacement created.")
    elif matches and not record.get("creating"):
        raise SyncError("Unmapped stable marker exists; explicit adoption required.")
    return matches[0] if matches else None


def find_item(items, issue, record):
    matches = [
        item for item in items if item.get("content") and item["content"].get("id") == issue["id"]
    ]
    if len(matches) > 1:
        raise SyncError("Duplicate Project membership.")
    item = matches[0] if matches else None
    if record.get("item_id") and (not item or item["id"] != record["item_id"]):
        raise SyncError("Mapped Project item removed/changed; no replacement created.")
    if item and item["isArchived"]:
        raise SyncError("Project item was archived; human reconciliation required.")
    return item


def plan(identifier: str, work, issue, item, record, path: Path, config):
    text = path.read_text(encoding="utf-8")
    link = field(text, "GitHub-Issue", optional=True)
    if not issue:
        if link:
            raise SyncError("Local backlink has no discovered issue; reconcile before creating.")
        if record.get("creating"):
            raise SyncError("Uncertain issue create not visible; inspect before retrying.")
        actions = ["create issue", "add Project item", "set " + work["stage"]]
        if work["lifecycle"][0] == "CLOSED":
            actions.append("close/" + work["lifecycle"][1])
    else:
        current = snapshot(issue, item, identifier)
        if record.get("creating") and not record.get("baseline"):
            expected = record["creating"]
            if (
                current["title"] != expected["title"]
                or current["managed"] != expected["managed"]
                or current["lifecycle"] != ["OPEN", None]
                or item
            ):
                raise SyncError("Recovered create differs from saved intent.")
        else:
            check_conflicts(current, record)
        actions = [
            "update " + key
            for key, target in desired_snapshot(work).items()
            if current[key] != target
        ]
        if not item:
            if record.get("adding_item"):
                raise SyncError("Uncertain Project add not visible; inspect before retrying.")
            actions.append("add Project item")
        if link is not None and not equivalent_issue_url(link, issue["url"], config):
            raise SyncError("Conflicting local backlink.")
    if not issue or link != issue["url"] or field(text, "Workstream-ID", True) != identifier:
        actions.append("write backlink")
    return actions


def verify_membership(item, issue, config):
    if (
        item["isArchived"]
        or item["project"]["id"] != config["project"]["id"]
        or not item["content"]
        or item["content"].get("id") != issue["id"]
    ):
        raise SyncError("Read-back Project membership mismatch.")


def synchronize(api, config, state, persist, identifier: str, path: Path, work, issue, item, root):
    record = state["workstreams"].setdefault(identifier, {})
    if issue:
        issue = api.issue(issue["id"])
        item = api.item(item["id"]) if item else None
        if item:
            verify_membership(item, issue, config)
        actions = plan(identifier, work, issue, item, record, path, config)
        if not actions and not any(
            record.get(flag) for flag in ("creating", "pending", "pending_origin", "adding_item")
        ):
            if parse_workstream(path, identifier, config, root) != work:
                raise SyncError("Local workstream changed during read-back.")
            return issue
    else:
        record["creating"] = {"title": work["title"], "managed": work["managed"]}
        persist()
        issue = api.create_issue(config["repository_id"], work["title"], work["body"])
    current = snapshot(issue, item, identifier)
    if not record.get("baseline"):
        record["baseline"] = current
    record.update(issue_id=issue["id"], number=issue["number"], url=issue["url"])
    record.pop("creating", None)
    # Retain the observed partial state if a later local target supersedes a pending one.
    record["pending_origin"] = current
    record["pending"] = desired_snapshot(work)
    persist()
    if current["title"] != work["title"] or current["managed"] != work["managed"]:
        old = managed_section(issue["body"], identifier)
        api.update_issue(issue["id"], work["title"], issue["body"].replace(old, work["body"], 1))
    if current["lifecycle"] != work["lifecycle"]:
        api.lifecycle(issue["id"], *work["lifecycle"])
    if not item:
        record["adding_item"] = True
        persist()
        item_id = api.add_item(config["project"]["id"], issue["id"])
        record["item_id"] = item_id
        record.pop("adding_item", None)
        persist()
        item = api.item(item_id)
    else:
        record["item_id"] = item["id"]
        record.pop("adding_item", None)
        persist()
    verify_membership(item, issue, config)
    if snapshot(issue, item, identifier)["status"] != work["status"]:
        api.set_status(
            config["project"]["id"],
            item["id"],
            config["project"]["status_field_id"],
            work["status"],
        )
    for attempt in range(3):
        verified_issue, verified_item = api.issue(issue["id"]), api.item(item["id"])
        verify_membership(verified_item, verified_issue, config)
        actual = snapshot(verified_issue, verified_item, identifier)
        if actual == desired_snapshot(work):
            break
        if attempt == 2:
            raise SyncError("Read-back differs; preserve pending operation and reconcile.")
        time.sleep(attempt + 1)
    if parse_workstream(path, identifier, config, root) != work:
        raise SyncError("Local workstream changed during apply; remote progress retained.")
    write_backlink(path, identifier, verified_issue["url"], config)
    text = path.read_text(encoding="utf-8")
    if (
        field(text, "GitHub-Issue") != verified_issue["url"]
        or field(text, "Workstream-ID") != identifier
    ):
        raise SyncError("Persistent local backlink verification failed.")
    record["baseline"] = actual
    record.pop("pending", None)
    record.pop("pending_origin", None)
    persist()
    return verified_issue


def run(config_path: Path, apply=False, selected=None, api=None, root=ROOT):
    config = load_json(config_path)
    if config["schema"] != 1 or config["todo_dir"] != "todo":
        raise SyncError("Unsupported configuration schema/TODO directory.")
    names = list(config["workstreams"].values())
    if len(names) != len(set(names)) or set(names) & set(config["exclude"]):
        raise SyncError("Duplicate or excluded configured workstream.")
    for identifier, name in config["workstreams"].items():
        if (
            not re.fullmatch(r"lea-\d{2}", identifier)
            or Path(name).name != name
            or not re.fullmatch(r"\d{2}_[A-Z0-9_]+\.todo", name)
        ):
            raise SyncError("Invalid stable identifier or numbered workstream filename.")
    selected = list(config["workstreams"]) if selected is None else selected
    if set(selected) - set(config["workstreams"]) or len(set(selected)) != len(selected):
        raise SyncError("Unknown or duplicate selected workstream.")
    state_path = root / config["state_file"]
    if (
        state_path.resolve().parent != (root / ".github").resolve()
        or state_path.suffix != ".json"
        or state_path.resolve() == config_path.resolve()
    ):
        raise SyncError("Mapping must be a separate JSON file inside .github.")
    state = (
        load_json(state_path)
        if state_path.exists()
        else {
            "schema": 1,
            "repository_id": config["repository_id"],
            "project_id": config["project"]["id"],
            "workstreams": {},
        }
    )
    if (
        state["schema"] != 1
        or state["repository_id"] != config["repository_id"]
        or state["project_id"] != config["project"]["id"]
    ):
        raise SyncError("Mapping identity mismatch.")
    api = api or GitHub()
    viewer, issues, items = api.inventory(config)
    print(
        f"{'APPLY' if apply else 'PREVIEW'} {config['repository']} as {viewer}; "
        + config["project"]["url"]
    )
    print(f"Inventory: {len(issues)} issues, {len(items)} Project items; {len(selected)} selected.")
    for name, why in config["exclude"].items():
        print(f"EXCLUDED {name}: {why}")
    known = set(names) | set(config["exclude"])
    for path in sorted((root / config["todo_dir"]).iterdir()):
        if path.is_file() and path.name not in known:
            print(f"UNADOPTED {path.name}: public-content and status review required; no writes.")
    for identifier in set(state["workstreams"]) - set(config["workstreams"]):
        print(f"ORPHANED {identifier}: mapping retained; no remote deletion.")
    errors = 0
    counts = {"created": 0, "reused": 0, "open": 0, "closed": 0, "verified": 0, "no_op": 0}
    for identifier in selected:
        try:
            path = root / config["todo_dir"] / config["workstreams"][identifier]
            work = parse_workstream(path, identifier, config, root)
            record = state["workstreams"].get(identifier, {})
            issue = find_issue(issues, identifier, record)
            if not issue and any(candidate["title"] == work["title"] for candidate in issues):
                raise SyncError("Unmapped matching title requires explicit identity review.")
            item = find_item(items, issue, record) if issue else None
            actions = plan(identifier, work, issue, item, record, path, config)
            print(
                f"{identifier} {path.name}: {', '.join(actions) if actions else 'no-op'}"
                f" -> {work['lifecycle']} / {work['stage']}"
            )
            if apply:
                existed = bool(issue)
                issue = synchronize(
                    api,
                    config,
                    state,
                    lambda: save_json(state_path, state),
                    identifier,
                    path,
                    work,
                    issue,
                    item,
                    root,
                )
                counts["reused" if existed else "created"] += 1
                counts["open" if issue["state"] == "OPEN" else "closed"] += 1
                counts["verified"] += 1
                counts["no_op"] += not actions
        except (SyncError, OSError, ValueError, KeyError) as error:
            errors += 1
            print(f"BLOCKED {identifier}: {error}", file=sys.stderr)
    print(json.dumps({"results": counts, "blocked": errors}, sort_keys=True))
    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / ".github" / "todo-sync.json")
    parser.add_argument(
        "--apply", action="store_true", help="Explicit issue/Project/backlink writes"
    )
    parser.add_argument(
        "--only", action="append", help="Stable workstream ID; repeat to select multiple"
    )
    args = parser.parse_args()
    try:
        if args.apply:
            with writer_lock(ROOT):
                return run(args.config, True, args.only)
        return run(args.config, False, args.only)
    except (SyncError, OSError, ValueError, KeyError) as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
