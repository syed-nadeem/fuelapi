from django.apps import AppConfig

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        # getting station geocoding in background on startup
        print("Strat processing station geocoding ")
        import threading
        from .data import load_stations
        t = threading.Thread(target=load_stations, daemon=True)
        t.start()
        print("End processing station geocoding ")
