"""
Infinite Anime/Manhwa - Backend (Flask + SQLite)

Ishga tushirish (kompyuteringizda):
    pip install -r requirements.txt
    python app.py
Sayt:   http://127.0.0.1:5000
Admin:  http://127.0.0.1:5000/admin   (parol: ADMIN_PASSWORD muhit o'zgaruvchisi)
"""
import os
import re
import uuid
import hmac
import shutil
import sqlite3
import secrets
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   session, g, flash, abort)
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "site.db"))
UPLOADS = os.path.join(BASE_DIR, "static", "uploads")
COVERS_DIR = os.path.join(UPLOADS, "covers")
PAGES_DIR = os.path.join(UPLOADS, "pages")
VIDEOS_DIR = os.path.join(UPLOADS, "videos")

IMAGE_EXT = {"jpg", "jpeg", "png", "webp"}
VIDEO_EXT = {"mp4", "webm"}

DEFAULT_PASSWORD = "infinite2026"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", DEFAULT_PASSWORD)


def load_secret_key():
    """SECRET_KEY muhit o'zgaruvchisidan, bo'lmasa .secret_key faylidan olinadi (bir marta yaratiladi)."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    path = os.path.join(BASE_DIR, ".secret_key")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(secrets.token_hex(32))
    with open(path) as f:
        return f.read().strip()


app = Flask(__name__)
app.config["SECRET_KEY"] = load_secret_key()
app.config["MAX_CONTENT_LENGTH"] = 600 * 1024 * 1024  # bir so'rovda jami 600 MB gacha
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# ---------------------------------------------------------------
# Ma'lumotlar bazasi
# ---------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    for d in (COVERS_DIR, PAGES_DIR, VIDEOS_DIR):
        os.makedirs(d, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('anime','manhwa')),
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'Davom etmoqda',
            genres TEXT DEFAULT '',
            cover TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
            number INTEGER NOT NULL,
            title TEXT DEFAULT '',
            video_url TEXT DEFAULT '',
            video_file TEXT DEFAULT '',
            images TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE (story_id, number)
        );
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    db.commit()
    db.close()


init_db()


# ---------------------------------------------------------------
# Xavfsizlik: admin kirish va CSRF himoyasi
# ---------------------------------------------------------------
def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


@app.context_processor
def inject_helpers():
    return {"csrf_token": csrf_token, "kind_word": kind_word}


@app.before_request
def check_csrf():
    if request.method == "POST":
        expected = session.get("csrf")
        sent = request.form.get("csrf_token", "")
        if not expected or not hmac.compare_digest(sent, expected):
            abort(400)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if hmac.compare_digest(request.form.get("password", ""), ADMIN_PASSWORD):
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Parol noto'g'ri.")
    return render_template("admin/login.html",
                           default_password=(ADMIN_PASSWORD == DEFAULT_PASSWORD))


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


# ---------------------------------------------------------------
# Yordamchi funksiyalar
# ---------------------------------------------------------------
def kind_word(kind):
    """anime -> 'qism', manhwa -> 'bob'"""
    return "qism" if kind == "anime" else "bob"


def ext_of(filename):
    return filename.rsplit(".", 1)[1].lower() if "." in filename else ""


def natural_key(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def normalize_genres(raw):
    parts = [p.strip() for p in raw.split(",")]
    return ",".join(p for p in parts if p)


def save_file(file_storage, folder, allowed):
    """Faylni xavfsiz nom bilan saqlaydi, saqlangan nomni qaytaradi ('' agar yaroqsiz)."""
    if not file_storage or not file_storage.filename:
        return ""
    ext = ext_of(secure_filename(file_storage.filename))
    if ext not in allowed:
        return ""
    name = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(folder, name))
    return name


def remove_quietly(path):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def delete_chapter_files(ch):
    if ch["video_file"]:
        remove_quietly(os.path.join(VIDEOS_DIR, ch["video_file"]))
    if ch["images"]:
        folder = ch["images"].split(",")[0].split("/")[0]
        remove_quietly(os.path.join(PAGES_DIR, folder))


def youtube_embed(url):
    """youtube.com/watch?v=ID yoki youtu.be/ID -> embed havola. YouTube bo'lmasa '' qaytaradi."""
    if not url:
        return ""
    m = re.search(r"(?:watch\?v=|youtu\.be/|/embed/)([A-Za-z0-9_-]{6,})", url)
    return f"https://www.youtube.com/embed/{m.group(1)}" if m else ""


def get_story_or_404(story_id):
    story = get_db().execute("SELECT * FROM stories WHERE id=?", (story_id,)).fetchone()
    if not story:
        abort(404)
    return story


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


@app.errorhandler(400)
def bad_request(_e):
    return render_template("404.html", message="So'rov noto'g'ri yoki sessiya eskirgan. "
                           "Sahifani yangilab, qayta urinib ko'ring."), 400


@app.errorhandler(413)
def too_large(_e):
    return render_template("404.html", message="Yuklanayotgan fayllar juda katta (600 MB dan oshdi)."), 413


# ---------------------------------------------------------------
# Ochiq sahifalar
# ---------------------------------------------------------------
@app.route("/")
def home():
    db = get_db()
    latest = db.execute("""
        SELECT c.id, c.number, s.id AS story_id, s.title, s.kind, s.cover
        FROM chapters c JOIN stories s ON s.id = c.story_id
        ORDER BY c.created_at DESC, c.id DESC LIMIT 8
    """).fetchall()
    news = db.execute("SELECT * FROM news ORDER BY created_at DESC, id DESC LIMIT 1").fetchone()
    return render_template("index.html", latest=latest, news=news)


def list_stories(kind, endpoint, title):
    db = get_db()
    q = request.args.get("q", "").strip()
    genre = request.args.get("genre", "").strip()
    sql = """SELECT s.*, (SELECT MAX(number) FROM chapters WHERE story_id = s.id) AS last_number
             FROM stories s WHERE s.kind = ?"""
    params = [kind]
    if q:
        sql += " AND s.title LIKE ?"
        params.append(f"%{q}%")
    if genre:
        sql += " AND (',' || s.genres || ',') LIKE ?"
        params.append(f"%,{genre},%")
    sql += " ORDER BY s.created_at DESC, s.id DESC"
    stories = db.execute(sql, params).fetchall()
    all_genres = sorted({g.strip() for row in
                         db.execute("SELECT genres FROM stories WHERE kind=?", (kind,))
                         for g in row["genres"].split(",") if g.strip()})
    return render_template("list.html", stories=stories, kind=kind, endpoint=endpoint,
                           page_title=title, q=q, genre=genre, genres=all_genres)


@app.route("/anime")
def anime_list():
    return list_stories("anime", "anime_list", "Anime")


@app.route("/manhwa")
def manhwa_list():
    return list_stories("manhwa", "manhwa_list", "Manhwa")


@app.route("/story/<int:story_id>")
def story_detail(story_id):
    story = get_story_or_404(story_id)
    chapters = get_db().execute(
        "SELECT * FROM chapters WHERE story_id=? ORDER BY number DESC", (story_id,)).fetchall()
    return render_template("story.html", story=story, chapters=chapters)


def chapter_context(chapter_id, expected_kind):
    db = get_db()
    chapter = db.execute("SELECT * FROM chapters WHERE id=?", (chapter_id,)).fetchone()
    if not chapter:
        abort(404)
    story = get_story_or_404(chapter["story_id"])
    if story["kind"] != expected_kind:
        abort(404)
    chapters = db.execute("SELECT * FROM chapters WHERE story_id=? ORDER BY number ASC",
                          (story["id"],)).fetchall()
    ids = [c["id"] for c in chapters]
    i = ids.index(chapter["id"])
    prev_ch = chapters[i - 1] if i > 0 else None
    next_ch = chapters[i + 1] if i < len(chapters) - 1 else None
    return chapter, story, chapters, prev_ch, next_ch


@app.route("/watch/<int:chapter_id>")
def watch_chapter(chapter_id):
    chapter, story, chapters, prev_ch, next_ch = chapter_context(chapter_id, "anime")
    return render_template("watch.html", chapter=chapter, story=story, chapters=chapters,
                           prev_ch=prev_ch, next_ch=next_ch,
                           embed=youtube_embed(chapter["video_url"]))


@app.route("/read/<int:chapter_id>")
def read_chapter(chapter_id):
    chapter, story, chapters, prev_ch, next_ch = chapter_context(chapter_id, "manhwa")
    images = [p for p in chapter["images"].split(",") if p]
    return render_template("reader.html", chapter=chapter, story=story, chapters=chapters,
                           prev_ch=prev_ch, next_ch=next_ch, images=images)


@app.route("/news")
def news():
    items = get_db().execute("SELECT * FROM news ORDER BY created_at DESC, id DESC").fetchall()
    return render_template("news.html", items=items)


# ---------------------------------------------------------------
# Admin panel
# ---------------------------------------------------------------
@app.route("/admin")
@login_required
def admin_dashboard():
    db = get_db()
    stories = db.execute("SELECT * FROM stories ORDER BY created_at DESC, id DESC").fetchall()
    chapters = {}
    for ch in db.execute("SELECT * FROM chapters ORDER BY number ASC"):
        chapters.setdefault(ch["story_id"], []).append(ch)
    news = db.execute("SELECT * FROM news ORDER BY created_at DESC, id DESC").fetchall()
    return render_template("admin/dashboard.html", stories=stories, chapters=chapters, news=news)


def story_form_values():
    kind = request.form.get("kind", "anime")
    if kind not in ("anime", "manhwa"):
        kind = "anime"
    return (request.form.get("title", "").strip(), kind,
            request.form.get("description", "").strip(),
            request.form.get("status", "Davom etmoqda").strip(),
            normalize_genres(request.form.get("genres", "")))


@app.route("/admin/story/new", methods=["GET", "POST"])
@login_required
def admin_story_new():
    if request.method == "POST":
        title, kind, desc, status, genres = story_form_values()
        if not title:
            flash("Sarlavha kiritilishi shart.")
            return render_template("admin/story_form.html", story=None)
        cover = save_file(request.files.get("cover"), COVERS_DIR, IMAGE_EXT)
        db = get_db()
        db.execute("INSERT INTO stories (title, kind, description, status, genres, cover) "
                   "VALUES (?,?,?,?,?,?)", (title, kind, desc, status, genres, cover))
        db.commit()
        flash("Hikoya qo'shildi. Endi unga qism/bob qo'shing.")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/story_form.html", story=None)


@app.route("/admin/story/<int:story_id>/edit", methods=["GET", "POST"])
@login_required
def admin_story_edit(story_id):
    story = get_story_or_404(story_id)
    if request.method == "POST":
        title, kind, desc, status, genres = story_form_values()
        if not title:
            flash("Sarlavha kiritilishi shart.")
            return render_template("admin/story_form.html", story=story)
        cover = story["cover"]
        new_cover = save_file(request.files.get("cover"), COVERS_DIR, IMAGE_EXT)
        if new_cover:
            if cover:
                remove_quietly(os.path.join(COVERS_DIR, cover))
            cover = new_cover
        db = get_db()
        db.execute("UPDATE stories SET title=?, kind=?, description=?, status=?, genres=?, cover=? "
                   "WHERE id=?", (title, kind, desc, status, genres, cover, story_id))
        db.commit()
        flash("Hikoya yangilandi.")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/story_form.html", story=story)


@app.route("/admin/story/<int:story_id>/delete", methods=["POST"])
@login_required
def admin_story_delete(story_id):
    story = get_story_or_404(story_id)
    db = get_db()
    for ch in db.execute("SELECT * FROM chapters WHERE story_id=?", (story_id,)):
        delete_chapter_files(ch)
    if story["cover"]:
        remove_quietly(os.path.join(COVERS_DIR, story["cover"]))
    db.execute("DELETE FROM stories WHERE id=?", (story_id,))
    db.commit()
    flash("Hikoya o'chirildi.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/story/<int:story_id>/chapter/new", methods=["GET", "POST"])
@login_required
def admin_chapter_new(story_id):
    story = get_story_or_404(story_id)
    db = get_db()
    next_number = (db.execute("SELECT MAX(number) FROM chapters WHERE story_id=?",
                              (story_id,)).fetchone()[0] or 0) + 1
    if request.method == "POST":
        try:
            number = int(request.form.get("number", ""))
        except ValueError:
            flash("Raqam noto'g'ri.")
            return render_template("admin/chapter_form.html", story=story, next_number=next_number)
        title = request.form.get("title", "").strip()
        video_url, video_file, images = "", "", ""

        if story["kind"] == "anime":
            video_url = request.form.get("video_url", "").strip()
            video_file = save_file(request.files.get("video_file"), VIDEOS_DIR, VIDEO_EXT)
            if not video_url and not video_file:
                flash("YouTube havolasini kiriting yoki video fayl yuklang.")
                return render_template("admin/chapter_form.html", story=story, next_number=next_number)
        else:
            files = [f for f in request.files.getlist("images") if f and f.filename]
            files.sort(key=lambda f: natural_key(f.filename))
            folder_name = f"{story_id}_{number}_{uuid.uuid4().hex[:6]}"
            os.makedirs(os.path.join(PAGES_DIR, folder_name), exist_ok=True)
            saved = []
            for i, f in enumerate(files, start=1):
                ext = ext_of(secure_filename(f.filename))
                if ext in IMAGE_EXT:
                    fname = f"page_{i:03d}.{ext}"
                    f.save(os.path.join(PAGES_DIR, folder_name, fname))
                    saved.append(f"{folder_name}/{fname}")
            if not saved:
                remove_quietly(os.path.join(PAGES_DIR, folder_name))
                flash("Kamida bitta rasm (jpg, png, webp) yuklang.")
                return render_template("admin/chapter_form.html", story=story, next_number=next_number)
            images = ",".join(saved)

        try:
            db.execute("INSERT INTO chapters (story_id, number, title, video_url, video_file, images) "
                       "VALUES (?,?,?,?,?,?)", (story_id, number, title, video_url, video_file, images))
            db.commit()
        except sqlite3.IntegrityError:
            if video_file:
                remove_quietly(os.path.join(VIDEOS_DIR, video_file))
            if images:
                remove_quietly(os.path.join(PAGES_DIR, images.split(",")[0].split("/")[0]))
            flash(f"{number}-{kind_word(story['kind'])} allaqachon mavjud.")
            return render_template("admin/chapter_form.html", story=story, next_number=next_number)
        flash(f"{number}-{kind_word(story['kind'])} qo'shildi.")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/chapter_form.html", story=story, next_number=next_number)


@app.route("/admin/chapter/<int:chapter_id>/delete", methods=["POST"])
@login_required
def admin_chapter_delete(chapter_id):
    db = get_db()
    ch = db.execute("SELECT * FROM chapters WHERE id=?", (chapter_id,)).fetchone()
    if not ch:
        abort(404)
    delete_chapter_files(ch)
    db.execute("DELETE FROM chapters WHERE id=?", (chapter_id,))
    db.commit()
    flash("O'chirildi.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/news/new", methods=["POST"])
@login_required
def admin_news_new():
    title = request.form.get("title", "").strip()
    if title:
        db = get_db()
        db.execute("INSERT INTO news (title, body) VALUES (?,?)",
                   (title, request.form.get("body", "").strip()))
        db.commit()
        flash("Yangilik qo'shildi.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/news/<int:news_id>/delete", methods=["POST"])
@login_required
def admin_news_delete(news_id):
    db = get_db()
    db.execute("DELETE FROM news WHERE id=?", (news_id,))
    db.commit()
    flash("Yangilik o'chirildi.")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    if ADMIN_PASSWORD == DEFAULT_PASSWORD:
        print("\n  DIQQAT: admin paroli standart ('infinite2026'). Real saytda "
              "ADMIN_PASSWORD muhit o'zgaruvchisini o'zgartiring!\n")
    app.run(debug=True)
