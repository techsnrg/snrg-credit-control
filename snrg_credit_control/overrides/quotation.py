from snrg_credit_control.credit_status import build_credit_snapshot, reset_credit_fields, stamp_credit_fields


def validate(doc, method=None):
    if not (doc.get("party_name") and doc.get("company")):
        reset_credit_fields(doc)
        return

    if doc.quotation_to != "Customer":
        reset_credit_fields(doc)
        return

    snapshot = build_credit_snapshot(
        customer=doc.party_name,
        company=doc.company,
        amount=doc.grand_total or doc.rounded_total,
        currency=doc.currency,
    )
    stamp_credit_fields(doc, snapshot)
