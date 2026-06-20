"""mkdocs hook: cross-reference registry + dynamic nav expansion.

Two related responsibilities, sharing a single front-matter scan per build:

1. **Cross-reference registry (`xref`)**: For every doc page that declares a
   `type` and `id`, expose `{title, url}` so templates can link to that page
   by ID without baking the target's title into the source. Available in
   templates as the Jinja global `xref`:

       {% set entry = xref.get('domain', {}).get('D015') %}
       {% if entry %}<a href="{{ base_url }}/{{ entry.url }}">{{ entry.title }}</a>{% endif %}

2. **Dynamic nav children**: When a nav section's index page declares both
   `index_of: <type>` and `nav_children: true`, every page of that type is
   appended as a child of that section, sorted by natural ID order, labelled
   by the page `id`. This keeps `tools/requirements-site/mkdocs.yml` free
   of generated entries — the sidebar reflects whatever pages currently
   exist in `docs/requirements/`.

A title change in any imported page propagates everywhere on the next
`mkdocs build` (linked-domain titles, index tables, sidebar labels) without
re-importing.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Populated in on_config, reused in on_env so the disk scan happens once per build.
_state: dict = {"by_type": {}, "meta_by_path": {}, "spec_index": []}

# Canonical spec section index. Point to your project's section-index YAML.
_SPEC_INDEX_REL = "sources/spec-section-index.yaml"  # rename to match your source document
# source → screen-image index (built by tools/requirements-site/scripts/build_screen_index.py)
# Add your project's source document IDs and their screen-image YAML files here.
# Format: {"SRC-EXAMPLE-001": "sources/{source-id}-screen-images.yaml"}
_SCREEN_INDEXES = {
    # "SRC-EXAMPLE-001": "sources/example-screen-images.yaml",
}
# Maps source document ID to the subfolder under assets/screens/ that holds its images.
# Format: {"SRC-EXAMPLE-001": "example"}
_SCREEN_FOLDERS = {
    # "SRC-EXAMPLE-001": "example",
}


def _screen_asset(source_id: str, section_id: str, idx: int) -> str:
    """Deterministic served path for a synced legacy-screen image. Must match
    tools/requirements-site/scripts/build_screen_index.py:asset_name."""
    folder = _SCREEN_FOLDERS.get(source_id, "misc")
    return f"assets/screens/{folder}/{section_id.replace('.', '-')}__{idx}.png"
# A spec section citation's `section` string starts with the chapter id, optionally prefixed
# by a document prefix like "§". Anchored at the start so free-text does NOT spuriously
# match a numeric id mid-string.
_SPEC_SECTION_RE = re.compile(r"^\s*(?:\w+\s*§?\s*)?(\d+(?:\.\d+)*)(?:\s|$)")

# The source document ID whose sections are tracked in the spec_section_index.
# Set this to the SRC-* ID of your primary specification document.
_SPEC_SOURCE_ID = "SRC-EXAMPLE-001"  # {PLACEHOLDER} replace with your spec document ID


def _spec_section_id(section_str):
    """Extract a canonical chapter id (e.g. '11.5.4') from a citation `section` string."""
    if not section_str:
        return None
    m = _SPEC_SECTION_RE.match(str(section_str))
    return m.group(1) if m else None


def _iter_spec_citations(meta):
    """Yield each spec section id cited by a page's `source` front matter.

    `source` may be a bare string, a single mapping, or a list of mappings shaped
    {document: SRC-EXAMPLE-001, section: "§<id>"}.
    """
    source = meta.get("source")
    if not source:
        return
    items = source if isinstance(source, list) else [source]
    for item in items:
        if isinstance(item, dict) and str(item.get("document")) == _SPEC_SOURCE_ID:
            sid = _spec_section_id(item.get("section"))
            if sid:
                yield sid


def _expand_req_ids(cell: str):
    """Expand a track.md Requirements cell into full REQ-<AREA>-<NNN> ids.

    The ledger is hand-written and uses a shorthand continuation where a leading
    area is stated once and later ids drop it, e.g.
        "REQ-NID-001, -002, -003, -010"  ->  REQ-NID-001, REQ-NID-002, …
    A bare "-NNN" token reuses the most recently seen "REQ-<AREA>-" prefix. Without
    this, a naive `REQ-[A-Z]+-\\d+` match silently drops every continuation id.
    """
    ids = []
    prefix = None
    for tok in re.findall(r"REQ-[A-Z]+-\d+|-\d+", cell):
        if tok.startswith("REQ-"):
            prefix = tok[: tok.rindex("-") + 1]
            ids.append(tok)
        elif prefix:
            ids.append(prefix + tok[1:])
    return ids


def _id_sort_key(id_value):
    """Natural-sort by dot-separated segments. Non-numeric segments sort after numerics."""
    parts = []
    for seg in str(id_value).split("."):
        try:
            parts.append((0, int(seg)))
        except ValueError:
            parts.append((1, seg))
    return parts


def _read_frontmatter(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


def _scan(docs_dir: Path):
    """Walk docs_dir and return ({type: sorted [(id, rel_path, meta)]}, {rel_path: meta})."""
    by_type: dict[str, list] = {}
    meta_by_path: dict[str, dict] = {}
    for md_path in docs_dir.rglob("*.md"):
        meta = _read_frontmatter(md_path)
        if not meta:
            continue
        rel = md_path.relative_to(docs_dir).as_posix()
        meta_by_path[rel] = meta
        page_type = meta.get("type")
        page_id = meta.get("id")
        if page_type and page_id:
            by_type.setdefault(str(page_type), []).append((str(page_id), rel, meta))
    for entries in by_type.values():
        entries.sort(key=lambda kv: _id_sort_key(kv[0]))
    return by_type, meta_by_path


def _build_spec_coverage(by_type, rel_to_url):
    """Compute per-section spec coverage from FEAT/REQ `source` citations.

    Returns {"sections": [...], "stats": {...}}. A section is `covered` when it is
    cited directly, or (for a parent chapter) when any descendant is cited. The
    must-cover denominator counts only `required` leaf sub-chapters.
    """
    index = _state.get("spec_index", [])
    if not index:
        return {"sections": [], "stats": {"required": 0, "covered": 0, "uncovered": 0, "pct": 0}}

    # section id -> list of citing pages
    citers: dict[str, list] = {str(s.get("id")): [] for s in index}
    for page_type in ("feature", "requirement"):
        for page_id, rel, meta in by_type.get(page_type, []):
            url = rel_to_url.get(rel)
            for sid in set(_iter_spec_citations(meta)):
                if sid in citers:
                    citers[sid].append({
                        "id": page_id,
                        "type": page_type,
                        "url": url,
                        "title": str(meta.get("title") or ""),
                    })

    ids = [str(s.get("id")) for s in index]
    direct = {sid: bool(citers[sid]) for sid in ids}

    def covered(sid, leaf):
        if direct[sid]:
            return True
        if leaf:
            return False
        prefix = sid + "."
        return any(direct[o] for o in ids if o.startswith(prefix))

    sections = []
    req_total = req_covered = 0
    for s in index:
        sid = str(s.get("id"))
        leaf = bool(s.get("leaf"))
        exp = s.get("coverage_expectation", "required")
        is_cov = covered(sid, leaf)
        if exp == "required" and leaf:
            req_total += 1
            if is_cov:
                req_covered += 1
        sections.append({
            "id": sid,
            "title": s.get("title", ""),
            "page": s.get("page"),
            "leaf": leaf,
            "expectation": exp,
            "citers": sorted(citers[sid], key=lambda c: c["id"]),
            "covered": is_cov,
        })

    pct = round(100 * req_covered / req_total) if req_total else 0
    return {
        "sections": sections,
        "stats": {
            "required": req_total,
            "covered": req_covered,
            "uncovered": req_total - req_covered,
            "pct": pct,
        },
    }


def on_config(config):
    """Scan front matter, then expand nav sections whose index opts in to nav_children."""
    docs_dir = Path(config["docs_dir"])
    by_type, meta_by_path = _scan(docs_dir)
    _state["by_type"] = by_type
    _state["meta_by_path"] = meta_by_path

    index_path = docs_dir / _SPEC_INDEX_REL
    spec_index = []
    if index_path.exists():
        try:
            loaded = yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
            spec_index = loaded.get("sections", []) or []
        except yaml.YAMLError:
            spec_index = []
    _state["spec_index"] = spec_index

    screen_indexes = {}
    for source_id, rel in _SCREEN_INDEXES.items():
        path = docs_dir / rel
        sections = {}
        if path.exists():
            try:
                sections = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get(
                    "sections", {}) or {}
            except yaml.YAMLError:
                sections = {}
        screen_indexes[source_id] = sections
    _state["screen_indexes"] = screen_indexes

    # Test coverage emitted by the test-author agents at
    # reports/test-coverage/<layer>/<REQ-ID>.json, keyed by requirement id with the
    # per-layer files merged. Loaded here (earliest event) so both on_env (Jinja
    # global) and on_page_content (per-page TOC entry) can rely on it.
    import json
    coverage: dict = {}
    cov_root = docs_dir.resolve().parents[1] / "reports" / "test-coverage"
    if cov_root.is_dir():
        for layer_dir in sorted(p for p in cov_root.iterdir() if p.is_dir()):
            for jf in sorted(layer_dir.glob("*.json")):
                try:
                    data = json.loads(jf.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    continue
                req = str(data.get("requirement") or jf.stem)
                coverage.setdefault(req, {})[layer_dir.name] = data
    _state["coverage"] = coverage

    # Implementation status + owner per requirement, parsed from the slice ledger
    # openspec/track.md — the SINGLE SOURCE OF TRUTH for both. Columns:
    # | Feature | Requirements | Change | Owner | Branch | Azure | Status | … |.
    # A row's `done` status marks its requirements as done; `in-progress`/`claimed`
    # marks them in-progress. Requirements absent from the ledger are open (and
    # unassigned). Done wins if a requirement appears in more than one row; the owner
    # tracked is the one from the winning row. Requirement md frontmatter intentionally
    # carries NEITHER value (see the guard below) — both the requirement page and the
    # product dashboard render these from here.
    req_status: dict = {}
    req_owner: dict = {}
    track = docs_dir.resolve().parents[1] / "openspec" / "track.md"
    if track.is_file():
        for line in track.read_text(encoding="utf-8").splitlines():
            if not line.lstrip().startswith("|"):
                continue
            cells = [c.strip() for c in line.split("|")]
            if len(cells) < 8:
                continue
            reqs_cell, owner_cell, status_cell = cells[2], cells[4], cells[7]
            if status_cell not in ("done", "in-progress", "claimed", "blocked"):
                continue
            # Internal status codes used by templates as CSS class keys.
            # status strings used by templates as CSS class keys
            # "done" = implemented, "in-progress" = in progress.
            state = "done" if status_cell == "done" else "in-progress"
            for rid in _expand_req_ids(reqs_cell):
                if req_status.get(rid) == "done":
                    continue
                if state == "done" or rid not in req_status:
                    req_status[rid] = state
                    if owner_cell and owner_cell.upper() != "TBD":
                        req_owner[rid] = owner_cell
                    else:
                        req_owner.pop(rid, None)
    _state["req_status"] = req_status
    _state["req_owner"] = req_owner

    # Single-source-of-truth guard. Implementation status + owner live ONLY in
    # openspec/track.md. A requirement's md frontmatter may carry a governance status
    # (draft/approved) and an unset owner (TBD or absent) — never an implementation
    # status (`in-progress`/`done`) nor a real owner name. Violations are logged as
    # warnings; `mkdocs build --strict` (the CI gate) turns any warning into a build
    # failure, so the two sources can no longer drift apart. See docs/requirements/AGENTS.md.
    import logging
    log = logging.getLogger("mkdocs.plugins.cross_refs")
    for page_id, rel, meta in by_type.get("requirement", []):
        status = str(meta.get("status") or "").strip()
        owner = str(meta.get("owner") or "").strip()
        if status in ("in-progress", "done"):
            log.warning(
                "%s: requirement `status: %s` is an implementation state — "
                "implementation status lives only in openspec/track.md. "
                "Use draft/approved here.",
                rel, status,
            )
        if owner and owner.upper() != "TBD":
            log.warning(
                "%s: requirement `owner: %s` — the implementation owner lives only in "
                "openspec/track.md (Owner column). Set `owner: TBD` (or omit) here.",
                rel, owner,
            )

    nav = config.get("nav")
    if not nav:
        return config

    def collect_existing(section_children: list) -> set:
        existing = set()
        for c in section_children:
            if isinstance(c, str):
                existing.add(c)
            elif isinstance(c, dict):
                for v in c.values():
                    if isinstance(v, str):
                        existing.add(v)
        return existing

    def expand(section_children: list) -> None:
        target_type = None
        index_path = None
        for c in section_children:
            rel = c if isinstance(c, str) else None
            if rel is None:
                continue
            meta = meta_by_path.get(rel)
            if not meta:
                continue
            if meta.get("index_of") and meta.get("nav_children"):
                index_path = rel
                target_type = str(meta["index_of"])
                break

        if not target_type:
            return

        existing = collect_existing(section_children)
        for pid, rel, _meta in by_type.get(target_type, []):
            if rel == index_path or rel in existing:
                continue
            section_children.append({pid: rel})

    def walk(items: list) -> None:
        for item in items:
            if isinstance(item, dict):
                for value in item.values():
                    if isinstance(value, list):
                        expand(value)
                        walk(value)

    walk(nav)
    return config


def on_env(env, config, files):
    """Expose the cross-reference registry as `xref` in the Jinja env."""
    by_type = _state["by_type"]

    rel_to_url = {
        f.src_uri: f.url for f in files if f.is_documentation_page()
    }

    xref: dict[str, dict[str, dict]] = {}
    for page_type, entries in by_type.items():
        bucket: dict[str, dict] = {}
        for page_id, rel, meta in entries:
            url = rel_to_url.get(rel)
            if not url:
                continue
            bucket[page_id] = {
                "title": str(meta.get("title") or ""),
                "url": url,
                # Expose the full front matter so templates (e.g. the index-of
                # partial) can pull arbitrary fields by name without each
                # consumer having to declare what it needs up front.
                "meta": meta,
            }
        xref[page_type] = bucket

    env.globals["xref"] = xref

    # Spec section coverage: map every indexed spec section to the FEAT/REQ pages that cite it,
    # so the source document page can render a "which sections are covered" matrix.
    env.globals["spec_coverage"] = _build_spec_coverage(by_type, rel_to_url)

    # Legacy-screen images: expose {source_id: {section_id: [{index, page, asset}]}}
    # so the screens.html partial can render the authoritative screenshot for a
    # requirement's `screens:` citation.
    
    screen_images = {}
    for source_id, sections in _state.get("screen_indexes", {}).items():
        screen_images[source_id] = {
            sid: [{"index": im["index"], "page": im.get("page"),
                   "asset": _screen_asset(source_id, sid, im["index"])}
                  for im in rec.get("images", [])]
            for sid, rec in sections.items()
        }
    env.globals["screen_images"] = screen_images

    # Register a `markdown` filter so partials can render small markdown
    # snippets inside YAML strings (e.g. each `change_history` entry, which
    # by convention starts with a bold date `**YYYY-MM-DD**:`). Without this
    # filter the bold/italics in those strings would render literally.
    import markdown as _md
    _md_inst = _md.Markdown(extensions=["extra"])

    def _md_filter(text):
        if text is None:
            return ""
        # Strip the wrapping <p>…</p> the markdown lib adds so the snippet
        # can sit inside a list item without breaking layout.
        html = _md_inst.reset().convert(str(text))
        if html.startswith("<p>") and html.endswith("</p>"):
            html = html[3:-4]
        return html

    env.filters["markdown"] = _md_filter

    # Coverage is loaded once in on_config (so on_page_markdown can use it too);
    # expose the merged-by-requirement registry to templates (the overview page).
    env.globals["test_coverage"] = _state.get("coverage", {})

    # Per-requirement implementation status + owner (from openspec/track.md, the single
    # source of truth — see on_config). Both the requirement header and the product
    # dashboard render these; requirement frontmatter no longer carries them.
    env.globals["req_impl_status"] = _state.get("req_status", {})
    env.globals["req_impl_owner"] = _state.get("req_owner", {})

    return env


def on_page_content(html, page, config, files):
    """Add a "Tests & coverage" entry to a requirement page's table of contents when
    it has coverage data. The section itself is rendered by the requirement header
    partial (between the link lists and the change history); template-rendered
    sections are not part of `page.toc`, so we add the TOC link here. Inserted at the
    top so its TOC position mirrors the section's position above the page body."""
    meta = getattr(page, "meta", {}) or {}
    if meta.get("type") != "requirement":
        return html
    if str(meta.get("id") or "") not in _state.get("coverage", {}):
        return html
    try:
        from mkdocs.structure.toc import AnchorLink
        try:
            link = AnchorLink("Tests & coverage", "tests-coverage", 2)
        except TypeError:  # older mkdocs AnchorLink signature
            link = AnchorLink("Tests & coverage", "tests-coverage")
        if not hasattr(link, "children"):
            link.children = []
        page.toc.items.insert(0, link)
    except Exception:
        pass
    return html
