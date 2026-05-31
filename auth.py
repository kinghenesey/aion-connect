# =============================================================
# AION Connect — Authentication
# =============================================================
from flask import (Blueprint, render_template, redirect,
                   url_for, flash, request)
from flask_login import login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from database import db, User

auth = Blueprint("auth", __name__)
bcrypt = Bcrypt()


@auth.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        # Validation
        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("register.html")

        if len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html")

        # Check duplicates
        if User.query.filter_by(username=username).first():
            flash("Username already taken.", "error")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "error")
            return render_template("register.html")

        # Create user
        hashed = bcrypt.generate_password_hash(password).decode("utf-8")
        user   = User(
            username=username,
            email=email,
            password=hashed,
            bio="Building with AION 🚀"
        )
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(f"Welcome to AION Connect, {username}!", "success")
        return redirect(url_for("main.home"))

    return render_template("register.html")


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(username=username).first()

        if not user or not bcrypt.check_password_hash(
            user.password, password
        ):
            flash("Invalid username or password.", "error")
            return render_template("login.html")

        login_user(user, remember=True)
        next_page = request.args.get("next")
        return redirect(next_page or url_for("main.home"))

    return render_template("login.html")


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))