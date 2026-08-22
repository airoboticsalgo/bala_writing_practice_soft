"""Login and logout routes."""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, url_for

from ..auth import is_logged_in, login_user, logout_user, verify_user

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if verify_user(username, password):
            login_user(username)
            return redirect(url_for("home.index"))
        error = "Invalid username or password."
    return render_template("login.html", error=error)


@bp.get("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
