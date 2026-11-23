"""Sanitized interaction content and owned, private interaction attachments."""
from urllib.parse import unquote
from bs4 import BeautifulSoup
import frappe
from frappe import _
from frappe.utils.html_utils import sanitize_html


def uploads(names):
    names = list(dict.fromkeys(names or []))
    if len(names) > 20:
        frappe.throw(_("Attach at most 20 files at a time."))
    files = []
    for name in names:
        file = frappe.get_doc("File", name)
        if file.owner != frappe.session.user or not file.is_private or file.attached_to_doctype or file.attached_to_name:
            frappe.throw(_("Choose your own private, unattached uploads."), frappe.PermissionError)
        if not (file.file_url or "").startswith("/private/files/"):
            frappe.throw(_("A private uploaded file is required."))
        files.append(file)
    return files


def clean(html, files):
    safe = sanitize_html(html or "", always_sanitize=True, disallowed_tags=["script", "style", "iframe", "object", "embed", "svg", "math", "video", "audio", "form", "input", "button", "meta", "link"])
    soup = BeautifulSoup(safe, "html.parser")
    urls = {unquote(file.file_url) for file in files}
    for image in soup.find_all("img"):
        if unquote(image.get("src", "")) not in urls:
            frappe.throw(_("Insert images using the private image upload button."))
    return safe


def attachment_rows(name, doctype="Customer Interaction"):
    return frappe.get_all("File", filters={"attached_to_doctype": doctype, "attached_to_name": name, "is_private": 1}, fields=["name", "file_name", "file_url"], order_by="creation", limit_page_length=0)


def attach_files(files, doc):
    for file in files:
        file.attached_to_doctype = doc.doctype
        file.attached_to_name = doc.name
        file.save(ignore_permissions=True)
