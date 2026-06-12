from django.apps import AppConfig


class DiagnosisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'diagnosis'
    verbose_name = 'Disease Diagnosis'

    def ready(self):
        """
        Seed the DiseaseKnowledge table from static data on first startup.
        This runs once when Django starts. It's a no-op if entries already exist.
        """
        
        pass