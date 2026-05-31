# =============================================================
# AION Connect — Database Models
# =============================================================
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(40), unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(200), nullable=False)
    bio        = db.Column(db.String(300), default="")
    avatar     = db.Column(db.String(200), default="")
    github     = db.Column(db.String(100), default="")
    website    = db.Column(db.String(200), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    projects  = db.relationship("Project", backref="author",
                                 lazy=True, cascade="all, delete")
    comments  = db.relationship("Comment", backref="author",
                                 lazy=True, cascade="all, delete")
    likes     = db.relationship("Like", backref="user",
                                 lazy=True, cascade="all, delete")
    following = db.relationship("Follow",
                                 foreign_keys="Follow.follower_id",
                                 backref="follower",
                                 lazy=True, cascade="all, delete")
    followers = db.relationship("Follow",
                                 foreign_keys="Follow.followed_id",
                                 backref="followed",
                                 lazy=True, cascade="all, delete")

    @property
    def follower_count(self):
        return len(self.followers)

    @property
    def following_count(self):
        return len(self.following)

    @property
    def project_count(self):
        return len(self.projects)

    def is_following(self, user):
        return Follow.query.filter_by(
            follower_id=self.id,
            followed_id=user.id
        ).first() is not None

    def __repr__(self):
        return f"<User {self.username}>"


class Project(db.Model):
    __tablename__ = "projects"

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), default="")
    code        = db.Column(db.Text, nullable=False)
    category    = db.Column(db.String(30), default="general")
    tags        = db.Column(db.String(200), default="")
    views       = db.Column(db.Integer, default=0)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow,
                             onupdate=datetime.utcnow)
    user_id     = db.Column(db.Integer,
                             db.ForeignKey("users.id"),
                             nullable=False)

    # Relationships
    comments = db.relationship("Comment", backref="project",
                                lazy=True, cascade="all, delete")
    likes    = db.relationship("Like", backref="project",
                                lazy=True, cascade="all, delete")

    @property
    def like_count(self):
        return len(self.likes)

    @property
    def comment_count(self):
        return len(self.comments)

    @property
    def tag_list(self):
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    def is_liked_by(self, user):
        if not user:
            return False
        return Like.query.filter_by(
            user_id=user.id,
            project_id=self.id
        ).first() is not None

    def __repr__(self):
        return f"<Project {self.title}>"


class Comment(db.Model):
    __tablename__ = "comments"

    id         = db.Column(db.Integer, primary_key=True)
    body       = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id    = db.Column(db.Integer,
                            db.ForeignKey("users.id"),
                            nullable=False)
    project_id = db.Column(db.Integer,
                            db.ForeignKey("projects.id"),
                            nullable=False)

    def __repr__(self):
        return f"<Comment {self.id}>"


class Like(db.Model):
    __tablename__ = "likes"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer,
                            db.ForeignKey("users.id"),
                            nullable=False)
    project_id = db.Column(db.Integer,
                            db.ForeignKey("projects.id"),
                            nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "project_id",
                            name="unique_like"),
    )


class Follow(db.Model):
    __tablename__ = "follows"

    id          = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer,
                             db.ForeignKey("users.id"),
                             nullable=False)
    followed_id = db.Column(db.Integer,
                             db.ForeignKey("users.id"),
                             nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("follower_id", "followed_id",
                            name="unique_follow"),
    )

class Message(db.Model):
    __tablename__ = "messages"

    id         = db.Column(db.Integer, primary_key=True)
    body       = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id    = db.Column(db.Integer,
                            db.ForeignKey("users.id"),
                            nullable=False)
    user       = db.relationship("User", backref="messages")

    def to_dict(self):
        return {
            "id":       self.id,
            "body":     self.body,
            "username": self.user.username,
            "avatar":   self.user.avatar or "",
            "time":     self.created_at.strftime("%H:%M"),
            "date":     self.created_at.strftime("%b %d"),
        }

class Notification(db.Model):
    __tablename__ = "notifications"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer,
                            db.ForeignKey("users.id"),
                            nullable=False)
    actor_id   = db.Column(db.Integer,
                            db.ForeignKey("users.id"),
                            nullable=False)
    type       = db.Column(db.String(20), nullable=False)
    # types: "like", "comment", "follow"
    project_id = db.Column(db.Integer,
                            db.ForeignKey("projects.id"),
                            nullable=True)
    message    = db.Column(db.String(200), nullable=False)
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime,
                            default=datetime.utcnow)

    # Relationships
    user    = db.relationship("User",
                               foreign_keys=[user_id],
                               backref="notifications")
    actor   = db.relationship("User",
                               foreign_keys=[actor_id])
    project = db.relationship("Project")

    def to_dict(self):
        return {
            "id":         self.id,
            "type":       self.type,
            "message":    self.message,
            "is_read":    self.is_read,
            "time":       self.created_at.strftime("%b %d, %Y"),
            "project_id": self.project_id,
            "actor":      self.actor.username,
            "avatar":     self.actor.avatar or "",
        }