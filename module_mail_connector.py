from gdo.base.GDO_Module import GDO_Module


class module_mail_connector(GDO_Module):
    """Inactive skeleton; no mailbox transport is registered yet."""

    def gdo_dependencies(self) -> list[str]:
        return ['mail']
