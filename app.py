# =============================================================
# AION Connect — Main Application v2.0
# =============================================================
import os
import uuid
from flask import (Blueprint, Flask, render_template,
                   redirect, url_for, flash, request,
                   jsonify)
from flask_login import (LoginManager, login_required,
                          current_user)
from flask_bcrypt import Bcrypt
from flask_socketio import SocketIO, emit, join_room
from dotenv import load_dotenv
from database import db, User, Project, Comment, Like, Follow, Message
from auth import auth, bcrypt

load_dotenv()

# ── App Factory ───────────────────────────────────────────────

socketio = SocketIO()

def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY", "aion-connect-secret-2026")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///aion_connect.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.path.join(
        os.path.dirname(__file__), "static", "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB

    # Create upload folder
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    bcrypt.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    app.register_blueprint(auth)
    app.register_blueprint(main)

    with app.app_context():
        db.create_all()
        _seed_data()

    return app


# ── Main Blueprint ────────────────────────────────────────────

main = Blueprint("main", __name__)


# ── Home / Feed ───────────────────────────────────────────────

@main.route("/")
def home():
    page     = request.args.get("page", 1, type=int)
    category = request.args.get("category", "all")
    sort     = request.args.get("sort", "latest")

    query = Project.query

    if category != "all":
        query = query.filter_by(category=category)

    if sort == "popular":
        projects = query.all()
        projects.sort(key=lambda p: p.like_count, reverse=True)
        projects = projects[(page-1)*12: page*12]
    elif sort == "trending":
        projects = query.all()
        projects.sort(key=lambda p: p.views, reverse=True)
        projects = projects[(page-1)*12: page*12]
    else:
        projects = query.order_by(
            Project.created_at.desc()
        ).paginate(page=page, per_page=12, error_out=False)
        projects = projects.items

    categories = ["all", "ai", "pipeline", "vision",
                  "voice", "web", "database", "general"]

    stats = {
        "projects": Project.query.count(),
        "users":    User.query.count(),
        "likes":    Like.query.count(),
    }

    return render_template("home.html",
        projects=projects,
        categories=categories,
        current_category=category,
        current_sort=sort,
        stats=stats
    )


# ── Explore ───────────────────────────────────────────────────

@main.route("/explore")
def explore():
    tag    = request.args.get("tag", "")
    search = request.args.get("q", "")
    page   = request.args.get("page", 1, type=int)

    query = Project.query

    if tag:
        query = query.filter(Project.tags.contains(tag))
    if search:
        query = query.filter(
            Project.title.contains(search) |
            Project.description.contains(search)
        )

    projects = query.order_by(
        Project.created_at.desc()
    ).paginate(page=page, per_page=16, error_out=False)

    all_projects = Project.query.all()
    tag_counts = {}
    for p in all_projects:
        for t in p.tag_list:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    popular_tags = sorted(
        tag_counts.items(), key=lambda x: x[1], reverse=True
    )[:15]

    return render_template("explore.html",
        projects=projects.items,
        popular_tags=popular_tags,
        current_tag=tag,
        search=search,
        total=projects.total
    )


# ── Project Detail ────────────────────────────────────────────

@main.route("/project/<int:project_id>")
def project(project_id):
    p = Project.query.get_or_404(project_id)
    p.views += 1
    db.session.commit()

    comments = Comment.query.filter_by(
        project_id=project_id
    ).order_by(Comment.created_at.asc()).all()

    related = Project.query.filter(
        Project.category == p.category,
        Project.id != p.id
    ).order_by(Project.created_at.desc()).limit(4).all()

    liked = p.is_liked_by(current_user) \
        if current_user.is_authenticated else False

    return render_template("project.html",
        project=p,
        comments=comments,
        related=related,
        liked=liked
    )


# ── Post Project ──────────────────────────────────────────────

@main.route("/post", methods=["GET", "POST"])
@login_required
def post():
    if request.method == "POST":
        title       = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        code        = request.form.get("code", "").strip()
        category    = request.form.get("category", "general")
        tags        = request.form.get("tags", "").strip()

        if not title or not code:
            flash("Title and code are required.", "error")
            return render_template("post.html")

        project = Project(
            title=title,
            description=description,
            code=code,
            category=category,
            tags=tags,
            user_id=current_user.id
        )
        db.session.add(project)
        db.session.commit()

        flash("Project shared successfully!", "success")
        return redirect(url_for("main.project",
                                project_id=project.id))

    return render_template("post.html")


# ── Profile ───────────────────────────────────────────────────

@main.route("/profile/<username>")
def profile(username):
    user     = User.query.filter_by(username=username).first_or_404()
    projects = Project.query.filter_by(
        user_id=user.id
    ).order_by(Project.created_at.desc()).all()

    is_following = False
    if current_user.is_authenticated and current_user.id != user.id:
        is_following = current_user.is_following(user)

    total_likes = sum(p.like_count for p in projects)
    total_views = sum(p.views for p in projects)

    return render_template("profile.html",
        user=user,
        projects=projects,
        is_following=is_following,
        total_likes=total_likes,
        total_views=total_views
    )


# ── Settings ──────────────────────────────────────────────────

@main.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        current_user.bio     = request.form.get("bio", "")[:300]
        current_user.github  = request.form.get("github", "")
        current_user.website = request.form.get("website", "")
        db.session.commit()
        flash("Profile updated!", "success")
        return redirect(url_for("main.profile",
                                username=current_user.username))

    return render_template("settings.html")


# ── Upload Avatar ─────────────────────────────────────────────

@main.route("/upload-avatar", methods=["POST"])
@login_required
def upload_avatar():
    if "avatar" not in request.files:
        flash("No file selected.", "error")
        return redirect(url_for("main.settings"))

    file = request.files["avatar"]

    if file.filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("main.settings"))

    # Validate extension
    allowed = {"png", "jpg", "jpeg", "gif", "webp"}
    ext = file.filename.rsplit(".", 1)[-1].lower()

    if ext not in allowed:
        flash("Only PNG, JPG, GIF, WEBP allowed.", "error")
        return redirect(url_for("main.settings"))

    # Save with unique filename
    filename = f"{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(
        os.path.dirname(__file__), "static", "uploads", filename)

    # Resize with Pillow
    try:
        from PIL import Image
        img = Image.open(file)
        img = img.convert("RGB")
        img.thumbnail((200, 200))
        img.save(filepath, quality=85, optimize=True)
    except Exception as e:
        flash(f"Image processing failed: {e}", "error")
        return redirect(url_for("main.settings"))

    # Delete old avatar
    if current_user.avatar:
        old_path = os.path.join(
            os.path.dirname(__file__),
            "static", "uploads",
            current_user.avatar)
        if os.path.exists(old_path):
            os.remove(old_path)

    current_user.avatar = filename
    db.session.commit()

    flash("Profile picture updated!", "success")
    return redirect(url_for("main.profile",
                            username=current_user.username))


# ── World Chat ────────────────────────────────────────────────

@main.route("/chat")
@login_required
def chat():
    messages = Message.query.order_by(
        Message.created_at.desc()
    ).limit(50).all()
    messages = list(reversed(messages))
    online_count = 1
    return render_template("chat.html",
        messages=messages,
        online_count=online_count
    )


# ── Delete Project ────────────────────────────────────────────

@main.route("/project/<int:project_id>/delete",
            methods=["POST"])
@login_required
def delete_project(project_id):
    p = Project.query.get_or_404(project_id)
    if p.user_id != current_user.id:
        flash("Not authorized.", "error")
        return redirect(url_for("main.home"))
    db.session.delete(p)
    db.session.commit()
    flash("Project deleted.", "success")
    return redirect(url_for("main.home"))


# ── API: Like ─────────────────────────────────────────────────

@main.route("/api/like/<int:project_id>", methods=["POST"])
@login_required
def like_project(project_id):
    p    = Project.query.get_or_404(project_id)
    like = Like.query.filter_by(
        user_id=current_user.id,
        project_id=project_id
    ).first()

    if like:
        db.session.delete(like)
        db.session.commit()
        return jsonify({"liked": False, "count": p.like_count})
    else:
        like = Like(user_id=current_user.id,
                    project_id=project_id)
        db.session.add(like)
        db.session.commit()
        return jsonify({"liked": True, "count": p.like_count})


# ── API: Comment ──────────────────────────────────────────────

@main.route("/api/comment/<int:project_id>", methods=["POST"])
@login_required
def add_comment(project_id):
    Project.query.get_or_404(project_id)
    body = request.json.get("body", "").strip()

    if not body or len(body) > 500:
        return jsonify({"error": "Invalid comment"}), 400

    comment = Comment(
        body=body,
        user_id=current_user.id,
        project_id=project_id
    )
    db.session.add(comment)
    db.session.commit()

    return jsonify({
        "id":       comment.id,
        "body":     comment.body,
        "username": current_user.username,
        "avatar":   current_user.avatar or "",
        "time":     comment.created_at.strftime("%b %d, %Y"),
    })


# ── API: Follow ───────────────────────────────────────────────

@main.route("/api/follow/<int:user_id>", methods=["POST"])
@login_required
def follow_user(user_id):
    if user_id == current_user.id:
        return jsonify({"error": "Cannot follow yourself"}), 400

    user   = User.query.get_or_404(user_id)
    follow = Follow.query.filter_by(
        follower_id=current_user.id,
        followed_id=user_id
    ).first()

    if follow:
        db.session.delete(follow)
        db.session.commit()
        return jsonify({
            "following": False,
            "count": user.follower_count
        })
    else:
        follow = Follow(
            follower_id=current_user.id,
            followed_id=user_id
        )
        db.session.add(follow)
        db.session.commit()
        return jsonify({
            "following": True,
            "count": user.follower_count
        })


# ── API: Run Code ─────────────────────────────────────────────

@main.route("/api/run", methods=["POST"])
def run_code():
    code = request.json.get("code", "")
    if not code.strip():
        return jsonify({"output": "", "error": None})

    lines = code.split("\n")
    outputs = []
    for line in lines:
        line = line.strip()
        if line.startswith("show "):
            val = line[5:].strip().strip('"').strip("'")
            outputs.append(val)
        elif line.startswith("think "):
            outputs.append("🧠 [AI response simulated]")

    output = "\n".join(outputs) if outputs else "// No output"
    return jsonify({"output": output, "error": None})


# ── WebSocket: Chat ───────────────────────────────────────────

@socketio.on("join")
def on_join(data):
    join_room("world")
    emit("status", {
        "msg": f"{data.get('username', 'Someone')} joined the chat"
    }, room="world")


@socketio.on("message")
def on_message(data):
    from flask_login import current_user
    from flask import current_app

    body     = data.get("body", "").strip()
    username = data.get("username", "Anonymous")
    avatar   = data.get("avatar", "")

    if not body or len(body) > 500:
        return

    # Save to database
    with current_app.app_context():
        try:
            user = User.query.filter_by(username=username).first()
            if user:
                msg = Message(body=body, user_id=user.id)
                db.session.add(msg)
                db.session.commit()
                msg_data = msg.to_dict()
            else:
                from datetime import datetime
                msg_data = {
                    "body":     body,
                    "username": username,
                    "avatar":   avatar,
                    "time":     datetime.utcnow().strftime("%H:%M"),
                    "date":     datetime.utcnow().strftime("%b %d"),
                }
        except Exception:
            from datetime import datetime
            msg_data = {
                "body":     body,
                "username": username,
                "avatar":   avatar,
                "time":     datetime.utcnow().strftime("%H:%M"),
                "date":     datetime.utcnow().strftime("%b %d"),
            }

    emit("message", msg_data, room="world")


# ── Seed Data ─────────────────────────────────────────────────

def _seed_data():
    if User.query.count() > 0:
        return

    from flask_bcrypt import generate_password_hash

    user = User(
        username="emmanuel_king",
        email="emmanuelkingchristopher@gmail.com",
        password=generate_password_hash("king.1225").decode("utf-8"),
        bio="Creator of AION — AI-Native Programming Language 🚀",
        github="kinghenesey",
    )
    db.session.add(user)
    db.session.flush()

    samples = [
        {
            "title": "Hello AION World",
            "description": "My first AION program — clean and simple.",
            "code": 'name = "World"\nshow "Hello, {name}!"\nshow "Welcome to AION!"',
            "category": "general",
            "tags": "beginner, hello-world",
        },
        {
            "title": "AI Market Analyzer",
            "description": "Uses the think keyword to analyze Nigerian fintech.",
            "code": 'think "Analyze the Nigerian fintech market in 2025"\n\nthought = think "What are the top 3 opportunities?"\nshow thought',
            "category": "ai",
            "tags": "ai, think, fintech, nigeria",
        },
        {
            "title": "Agent Research Pipeline",
            "description": "Chains AI agents together for deep research.",
            "code": '"African tech ecosystem 2025" -> researcher -> analyst -> writer',
            "category": "pipeline",
            "tags": "pipeline, agents, research, ai",
        },
        {
            "title": "Neural Market Report",
            "description": "Full neural pipeline — collect, process, generate, save.",
            "code": 'pipeline market_report:\n    collect "Nigerian startup ecosystem"\n    process with ai\n    generate report\n    save to database\n\nrun pipeline market_report',
            "category": "pipeline",
            "tags": "pipeline, neural, report, ai",
        },
        {
            "title": "Vision Image Analyzer",
            "description": "Analyzes images using Gemini vision.",
            "code": 'use vision\n\ndescription = vision_scan("photo.png")\nshow "AI sees: {description}"',
            "category": "vision",
            "tags": "vision, multimodal, gemini, image",
        },
        {
            "title": "Voice Assistant",
            "description": "AION speaks and listens.",
            "code": 'use voice\n\nvoice_speak("Hello! I am AION.")\ntranscript = voice_listen()\nshow "You said: {transcript}"',
            "category": "voice",
            "tags": "voice, audio, multimodal, tts",
        },
    ]

    for s in samples:
        p = Project(user_id=user.id, **s)
        db.session.add(p)

    db.session.commit()


# ── Entry Point ───────────────────────────────────────────────

if __name__ == "__main__":
    app = create_app()
    print("\n  ⬡ AION Connect v2.0")
    print("  ─────────────────────────────")
    print("  ✓ Running at http://localhost:5000")
    print("  ✓ World Chat enabled")
    print("  ✓ Profile pictures enabled")
    print("  ✓ Default login: emmanuel / aion2026")
    print("  Press Ctrl+C to stop\n")
    socketio.run(app, debug=True, port=5000,
                 allow_unsafe_werkzeug=True)