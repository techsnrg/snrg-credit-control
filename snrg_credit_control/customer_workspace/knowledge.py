"""Teamspace Knowledge. All access goes through the workspace's permission checks."""


import base64
import binascii
from html import escape
from io import BytesIO
import re
from urllib.parse import urlencode, urlsplit

import frappe
from frappe import _
from frappe.utils import add_months, getdate, today
from bs4 import BeautifulSoup
from PIL import Image
from werkzeug.utils import secure_filename, send_file
from frappe.utils.file_manager import save_file

from . import api, rich_text

GUIDE = "Teamspace Guide"
REVISION = "Teamspace Guide Revision"
DETAIL_FIELDS = [
    "name", "title", "department", "guide_owner", "audience_role",
    "reference_doctype", "published_revision", "working_revision", "reviewed_on",
    "review_due", "pending_review",
]


def can_edit(guide):
    return api.manager() or guide.guide_owner == frappe.session.user


def in_audience(guide):
    return can_edit(guide) or not guide.audience_role or guide.audience_role in frappe.get_roles()


def get_guide(name, write=False):
    api.guard()
    guide = frappe.get_doc(GUIDE, name, for_update=write)
    if not in_audience(guide) or (not can_edit(guide) and (write or not guide.published_revision)):
        frappe.throw(_("You do not have access to this guide."), frappe.PermissionError)
    return guide


def revision_body(name):
    return frappe.db.get_value(REVISION, name, "body") if name else ""


def summary(row):
    return {
        "name": row.name, "title": row.title, "department": row.department,
        "owner": frappe.utils.get_fullname(row.guide_owner), "reviewed_on": row.reviewed_on,
        "published": bool(row.published_revision),
        "review_due": row.review_due,
        "review_overdue": bool(row.review_due and getdate(row.review_due) <= getdate(today())),
        "pending_review": bool(row.pending_review and can_edit(row)),
    }


@frappe.whitelist()
def search(query="", reference_doctype=None):
    if reference_doctype and not api.internal():
        return []
    api.guard()
    rows = frappe.get_all(
        GUIDE,
        filters={"reference_doctype": reference_doctype} if reference_doctype else {},
        fields=DETAIL_FIELDS, order_by="title asc", limit_page_length=0,
    )
    query = (query or "").strip().casefold()
    results = []
    for row in rows:
        if not in_audience(row) or (not row.published_revision and (reference_doctype or not can_edit(row))):
            continue
        card = summary(row)
        if query or not reference_doctype:
            document = BeautifulSoup(revision_body(row.published_revision), "html.parser")
            body = document.get_text(" ", strip=True)
            if query and query not in " ".join((row.title, row.department, body)).casefold():
                continue
            paragraph = document.find("p")
            excerpt = paragraph.get_text(" ", strip=True) if paragraph else body
            card["excerpt"] = excerpt if len(excerpt) <= 170 else excerpt[:170].rsplit(" ", 1)[0] + "…"
        results.append(card)
    return results


def revision_sections(name):
    if not name:
        return []
    return frappe.parse_json(frappe.db.get_value(REVISION, name, "sections_json") or "[]")


VIDEO_LIMIT = 50 * 1024 * 1024
VIDEO_TYPES = {".mp4": "video/mp4", ".webm": "video/webm"}


def video_file(guide, file_name):
    doc = frappe.get_doc("File", file_name)
    if not doc.is_private or doc.attached_to_doctype != GUIDE or doc.attached_to_name != guide:
        frappe.throw(_("This video does not belong to the guide."), frappe.PermissionError)
    return doc


@frappe.whitelist(methods=["POST"])
def upload_section_video(name):
    guide = get_guide(name, write=True)
    upload = frappe.request.files.get("file")
    filename = secure_filename(upload.filename or "") if upload else ""
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in VIDEO_TYPES:
        frappe.throw(_("Choose an MP4 or WebM video."))
    content = upload.stream.read(VIDEO_LIMIT + 1)
    if len(content) > VIDEO_LIMIT:
        frappe.throw(_("Choose a video up to 50 MB."))
    if not (content[4:8] == b"ftyp" if suffix == ".mp4" else content.startswith(bytes.fromhex("1a45dfa3"))):
        frappe.throw(_("The selected file does not match its video format."))
    doc = save_file(filename, content, GUIDE, guide.name, is_private=1)
    return {"name": doc.name, "filename": doc.file_name}


@frappe.whitelist(methods=["GET"])
def section_video(name, file):
    guide = get_guide(name)
    revisions = [guide.published_revision]
    if can_edit(guide):
        revisions.append(guide.working_revision)
    if not any(section.get("video_file") == file for rev in revisions for section in revision_sections(rev)):
        frappe.throw(_("This video is unavailable."), frappe.PermissionError)
    doc = video_file(guide.name, file)
    media_type = VIDEO_TYPES.get("." + doc.file_name.rsplit(".", 1)[-1].lower())
    if not media_type:
        frappe.throw(_("This video format is unavailable."))
    response = send_file(BytesIO(doc.get_content()), frappe.request.environ, mimetype=media_type,
                         download_name=doc.file_name, conditional=True, max_age=0)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def reader_sections(guide, revision):
    sections = revision_sections(revision)
    for section in sections:
        if section.get("video_file"):
            section["video_src"] = "/api/method/" + __name__ + ".section_video?" + urlencode({
                "name": guide, "file": section["video_file"],
            })
    return sections


def clean_sections(value, guide=None):
    items = frappe.parse_json(value)
    if not isinstance(items, list) or not 1 <= len(items) <= 24:
        frappe.throw(_("Use between 1 and 24 sections."))
    result = []
    seen = set()
    image_bytes = 0
    for item in items:
        key, title = item.get("id", ""), item.get("title", "").strip()
        if not re.fullmatch(r"[a-z0-9-]{1,64}", key) or key in seen or not 1 <= len(title) <= 140:
            frappe.throw(_("Give every section its own heading."))
        seen.add(key)
        section = {"id": key, "title": title, "body": rich_text.clean(item.get("body", ""), [])}
        if item.get("image"):
            url = item["image"]
            match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)", url) if len(url) <= 2800000 else None
            if not match:
                frappe.throw(_("Choose a PNG, JPEG, or WebP screenshot under 2 MB."))
            try:
                content = base64.b64decode(match[2], validate=True)
                with Image.open(BytesIO(content)) as picture:
                    if picture.format.lower() != match[1] or picture.width * picture.height > 16000000:
                        raise ValueError()
                    picture.verify()
            except (ValueError, OSError, binascii.Error, Image.DecompressionBombError):
                frappe.throw(_("The screenshot is invalid or too large."))
            image_bytes += len(content)
            if image_bytes > 3000000:
                frappe.throw(_("Keep screenshots under 3 MB per guide in total."))
            alt = (item.get("alt") or "").strip()
            if not alt or len(alt) > 250:
                frappe.throw(_("Describe each screenshot in up to 250 characters."))
            section.update(image=url, alt=alt, caption=(item.get("caption") or "").strip()[:500],
                           layout="beside" if item.get("layout") == "beside" else "full")
        video_url = (item.get("video_url") or "").strip()
        file_name = item.get("video_file")
        if file_name:
            doc = video_file(guide, file_name)
            section.update(video_file=doc.name, video_filename=doc.file_name)
        elif video_url:
            try:
                video = urlsplit(video_url)
                valid = (video.scheme == "https" and video.hostname and not video.username
                         and not video.password and not re.search(r"[\s\\<>]", video_url)
                         and video.path.lower().endswith((".mp4", ".webm")))
            except ValueError:
                valid = False
            if not valid or len(video_url) > 2048:
                frappe.throw(_("Enter a direct HTTPS link to an MP4 or WebM video."))
            section["video_url"] = video_url
        if file_name or video_url:
            text_kind = item.get("video_text_kind")
            video_text = (item.get("video_text") or "").strip()
            if text_kind not in ("Transcript", "Written summary") or not 1 <= len(video_text) <= 12000:
                frappe.throw(_("Add a transcript or written summary of up to 12,000 characters."))
            section.update(video_text_kind=text_kind, video_text=video_text)
        result.append(section)
    return result


@frappe.whitelist()
def read(name):
    guide = get_guide(name)
    result = {
        **summary(guide), "body": revision_body(guide.published_revision),
        "can_edit": can_edit(guide),
        "sections": reader_sections(guide.name, guide.published_revision),
    }
    if result["can_edit"]:
        result.update(
            draft=revision_body(guide.working_revision), version=str(guide.modified),
            can_publish=api.manager(), change_summary=guide.change_summary,
            draft_sections=reader_sections(guide.name, guide.working_revision),
        )
    return result


@frappe.whitelist(methods=["POST"])
def save_draft(name, version, body="", change_summary=None, sections=None):
    guide = get_guide(name, write=True)
    check_version(guide, version)
    structured = clean_sections(sections, guide.name) if sections is not None else []
    if structured:
        body = "".join(f'<h2>{escape(section["title"])}</h2>{section["body"]}' for section in structured)
    if not isinstance(body, str) or len(body) > 80000:
        frappe.throw(_("The guide is too long."))
    body = rich_text.clean(body, [])
    if not BeautifulSoup(body, "html.parser").get_text(strip=True):
        frappe.throw(_("Enter the guide instructions."))
    draft = frappe.get_doc({"doctype": REVISION, "guide": guide.name, "body": body,
                            "sections_json": frappe.as_json(structured) if structured else None})
    draft.insert(ignore_permissions=True)
    previous_draft = guide.working_revision
    guide.working_revision = draft.name
    if change_summary is not None:
        guide.change_summary = (change_summary or "").strip()[:1000]
    guide.save(ignore_permissions=True)
    if previous_draft:
        frappe.delete_doc(REVISION, previous_draft, ignore_permissions=True)
    return read(name)


def check_version(guide, version):
    if str(guide.modified) != version:
        frappe.throw(_("This guide changed. Reopen it before saving or publishing."))


@frappe.whitelist(methods=["POST"])
def publish(name, version):
    if not api.manager():
        frappe.throw(_("A Teamspace manager must publish this guide."), frappe.PermissionError)
    guide = get_guide(name, write=True)
    check_version(guide, version)
    if not guide.working_revision:
        frappe.throw(_("Save a draft before publishing."))
    guide.published_revision = guide.working_revision
    guide.working_revision = None
    guide.reviewed_on = today()
    guide.review_due = add_months(today(), 6)
    guide.pending_review = 0
    guide.save(ignore_permissions=True)
    return read(name)


@frappe.whitelist()
def guide_options():
    api.guard()
    if not api.manager():
        frappe.throw(_("A Teamspace manager must create guides."), frappe.PermissionError)
    people = [{"user": row.user_id, "label": row.employee_name} for row in api._directory() if row.can_notify]
    if not any(row["user"] == frappe.session.user for row in people):
        people.append({"user": frappe.session.user, "label": frappe.utils.get_fullname()})
    return {
        "people": people,
        "roles": frappe.get_all("Role", filters={"disabled": 0, "desk_access": 1}, pluck="name", order_by="name"),
    }


@frappe.whitelist(methods=["POST"])
def create(title, department, owner=None, audience_role=None, reference_doctype=None):
    options = guide_options()
    title, department = (title or "").strip(), (department or "").strip()
    if not title or not department or max(len(title), len(department)) > 140:
        frappe.throw(_("Enter a title and department, each up to 140 characters."))
    owner = owner or frappe.session.user
    if not any(row["user"] == owner for row in options["people"]):
        frappe.throw(_("Choose an active Teamspace member as owner."))
    if audience_role and audience_role not in options["roles"]:
        frappe.throw(_("Choose an internal role."))
    if reference_doctype not in (None, "", "Customer"):
        frappe.throw(_("Choose a supported ERPNext form."))
    guide = frappe.get_doc({
        "doctype": GUIDE, "title": title, "department": department, "guide_owner": owner,
        "reference_doctype": reference_doctype or None, "audience_role": audience_role or None,
    }).insert(ignore_permissions=True)
    return read(guide.name)


@frappe.whitelist(methods=["POST"])
def request_review(name, version):
    guide = get_guide(name, write=True)
    check_version(guide, version)
    if not guide.working_revision:
        frappe.throw(_("Save a draft before requesting review."))
    guide.pending_review = 1
    guide.save(ignore_permissions=True)
    return read(name)


@frappe.whitelist(methods=["POST"])
def suggest(name, note):
    guide = get_guide(name)
    note = (note or "").strip()
    if not guide.published_revision or not 1 <= len(note) <= 2000:
        frappe.throw(_("Enter a correction of up to 2,000 characters for a published guide."))
    link = "/teamspace?guide=" + guide.name
    task = api.create_action({
        "assigned_to": guide.guide_owner, "subject": _("Review guide correction: {0}").format(guide.title)[:140],
        "description": f"{note}\n\n{link}", "due_date": today(), "priority": "Medium",
        "action_type": "Follow-up",
    })
    return task["name"]
