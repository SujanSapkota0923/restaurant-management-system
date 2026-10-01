from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Cross-cutting technical code. Holds no domain model and no business rule."""

    name = "rms.core"
    label = "rms_core"
