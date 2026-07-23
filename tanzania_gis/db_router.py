"""Elekeza apps za detailed_planning + land_conflicts kwenye database DETAILED PLANNING."""


class DetailedPlanningRouter:
    """Apps zinazotumia database alias 'detailed_planning'."""

    route_app_labels = {'detailed_planning', 'land_conflicts'}

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return 'detailed_planning'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return 'detailed_planning'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        a1 = obj1._meta.app_label
        a2 = obj2._meta.app_label
        if a1 in self.route_app_labels or a2 in self.route_app_labels:
            # Ruhusu tu ndani ya apps za detailed_planning DB (hakuna FK cross-DB)
            return a1 in self.route_app_labels and a2 in self.route_app_labels
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == 'detailed_planning':
            return app_label in self.route_app_labels
        if app_label in self.route_app_labels:
            return False
        return None
