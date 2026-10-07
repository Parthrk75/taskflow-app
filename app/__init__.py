import os
import socket
from datetime import date

from flask import Flask, render_template

from .config import Config
from .db import close_db, init_db
from .routes import bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.register_blueprint(bp)
    app.teardown_appcontext(close_db)

    @app.context_processor
    def inject_globals():
        return {
            "hostname": os.getenv("POD_NAME") or socket.gethostname(),
            "app_version": app.config["APP_VERSION"],
            "today": date.today(),
        }

    @app.errorhandler(404)
    def not_found(_):
        return render_template("error.html", code=404, message="That page could not be found."), 404

    @app.errorhandler(500)
    def server_error(_):
        return render_template("error.html", code=500, message="Something went wrong on our side."), 500

    if not os.getenv("SKIP_DB_INIT"):
        init_db(app)

    return app
