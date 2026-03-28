from snrg_credit_control import setup


def execute():
    setup._ensure_module()
    setup._ensure_report()
    setup._ensure_demand_notice_settings()
    setup._ensure_credit_control_workspace()
