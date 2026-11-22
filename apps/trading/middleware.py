from .autorun import ensure_started


class AutorunMiddleware:
    """Demarre l'analyse automatique a la premiere requete du site (puis ne fait plus rien)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ensure_started()
        return self.get_response(request)
