from snrg_credit_control.cheque_bounce import sync_cheque_bounce_case_from_journal_entry


def on_update_after_submit(doc, method=None):
    sync_cheque_bounce_case_from_journal_entry(doc)


def on_submit(doc, method=None):
    sync_cheque_bounce_case_from_journal_entry(doc)
