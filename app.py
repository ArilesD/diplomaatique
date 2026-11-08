from flask import Flask

from controllers.arrete_controller import blueprint_arretes


def creer_application() -> Flask:
    """Crée et configure l'application Flask."""
    application = Flask(
        __name__,
        template_folder="views",
        static_folder="views",
        static_url_path="/views",
    )
    application.register_blueprint(blueprint_arretes)
    return application


if __name__ == "__main__":
    app = creer_application()
    app.run(host="127.0.0.1")
