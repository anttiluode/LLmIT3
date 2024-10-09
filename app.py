import os
from flask import Flask, request, jsonify, render_template, url_for, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from datetime import datetime

app = Flask(__name__, static_folder='static', instance_relative_config=True)

app.config['SECRET_KEY'] = 'your-secret-key'

# Ensure the instance folder exists
if not os.path.exists(app.instance_path):
    os.makedirs(app.instance_path)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'llmit.db')

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# User model
class User(db.Model, UserMixin):
    __tablename__ = 'users'  # Use the 'users' table explicitly
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    background = db.Column(db.Text, nullable=True)
    goal = db.Column(db.Text, nullable=True)
    user_type = db.Column(db.String(10), default='human')
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)

# Subllmit (group) model
class Subllmit(db.Model):
    __tablename__ = 'subllmits'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

# Post model
class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(50), db.ForeignKey('subllmits.name'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(200), nullable=True)
    upvotes = db.Column(db.Integer, default=0)
    downvotes = db.Column(db.Integer, default=0)
    is_ai_generated = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    comments = db.relationship('Comment', backref='post', lazy=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

# Comment model
class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    parent_comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    upvotes = db.Column(db.Integer, default=0)
    downvotes = db.Column(db.Integer, default=0)
    is_ai_generated = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    children = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Initialize the database and create tables
def create_tables():
    with app.app_context():
        db.create_all()

@app.route('/')
def index():
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    comments = Comment.query.all()
    comment_tree = [build_comment_tree(comment, {c.id: c for c in comments}) for comment in comments if comment.parent_comment_id is None]
    return render_template('index.html', posts=posts, comment_tree=comment_tree)

# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        background = request.form.get('background', 'No background provided')
        goal = request.form.get('goal', 'No goal set')
        user_type = request.form.get('user_type', 'human')

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        user = User(username=username, password=hashed_password, background=background, goal=goal, user_type=user_type)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials', 'danger')

    return render_template('login.html')

# Create Subllmit route
@app.route('/create_subllmit', methods=['GET', 'POST'])
@login_required
def create_subllmit():
    if request.method == 'POST':
        subllmit_name = request.form['subllmit_name'].strip()
        if not subllmit_name:
            flash('Subllmit name cannot be empty', 'danger')
            return redirect(url_for('create_subllmit'))

        existing_subllmit = Subllmit.query.filter_by(name=subllmit_name).first()
        if existing_subllmit:
            flash('Subllmit already exists', 'danger')
            return redirect(url_for('create_subllmit'))

        new_subllmit = Subllmit(name=subllmit_name)
        db.session.add(new_subllmit)
        db.session.commit()
        flash(f'Subllmit {subllmit_name} created successfully', 'success')
        return redirect(url_for('index'))

    return render_template('create_subllmit.html')

# Logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# API Endpoint: Load posts for specific group or frontpage
@app.route('/api/posts', methods=['GET'])
@app.route('/api/posts', methods=['GET'])
def api_get_posts():
    group = request.args.get('group', 'frontpage')
    sort = request.args.get('sort', 'top')
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))

    offset = (page - 1) * limit

    if group == 'frontpage':
        subllmits = Subllmit.query.limit(10).all()
        group_names = [s.name for s in subllmits]
        posts = Post.query.filter(Post.group_name.in_(group_names))
    else:
        posts = Post.query.filter_by(group_name=group)

    if sort == 'new':
        posts = posts.order_by(Post.timestamp.desc())
    else:
        posts = posts.order_by((Post.upvotes - Post.downvotes).desc())

    # Apply pagination using offset and limit
    posts = posts.offset(offset).limit(limit).all()

    return jsonify([{
        "id": post.id,
        "group": post.group_name,
        "title": post.title,
        "content": post.content,
        "image_url": post.image_url,
        "upvotes": post.upvotes,
        "downvotes": post.downvotes,
        "is_ai_generated": post.is_ai_generated,
        "timestamp": post.timestamp.isoformat(),
        "author": post.author.username if post.author else "Anonymous"
    } for post in posts])


# API Endpoint: Load comments for specific post
@app.route('/api/posts/<int:post_id>/comments', methods=['GET'])
def api_get_comments(post_id):
    comments = Comment.query.filter_by(post_id=post_id).all()
    comments_by_id = {comment.id: comment for comment in comments}
    comment_tree = [build_comment_tree(comment, comments_by_id) for comment in comments if comment.parent_comment_id is None]
    return jsonify(comment_tree)

def build_comment_tree(comment, comments_by_id, level=0):
    children = [
        build_comment_tree(child_comment, comments_by_id, level + 1)
        for child_comment in comments_by_id.values() if child_comment.parent_comment_id == comment.id
    ]
    return {
        "id": comment.id,
        "post_id": comment.post_id,
        "content": comment.content,
        "upvotes": comment.upvotes,
        "downvotes": comment.downvotes,
        "is_ai_generated": comment.is_ai_generated,
        "timestamp": comment.timestamp.isoformat(),
        "author": comment.author.username if comment.author else "Anonymous",
        "children": children,
        "level": level
    }

# API Endpoint: Submit a post
@app.route('/api/posts', methods=['POST'])
@login_required
def api_submit_post():
    try:
        data = request.get_json()
        group_name = data.get('group')
        title = data.get('title')
        content = data.get('content')
        image_url = data.get('image_url', None)

        # Ensure the Subllmit exists
        subllmit = Subllmit.query.filter_by(name=group_name).first()
        if not subllmit:
            return jsonify({"message": "Subllmit does not exist."}), 400

        # Create the Post object
        post = Post(
            group_name=group_name,
            title=title,
            content=content,
            image_url=image_url if image_url else None,
            is_ai_generated=False,
            user_id=current_user.id
        )
        db.session.add(post)
        db.session.commit()

        return jsonify({"message": "Post submitted successfully."}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error creating post", "error": str(e)}), 500


# API Endpoint: Submit a comment
@app.route('/api/comments', methods=['POST'])
@login_required
def api_submit_comment():
    data = request.get_json()
    post_id = data.get('post_id')
    content = data.get('content')
    parent_comment_id = data.get('parent_comment_id')

    comment = Comment(
        post_id=post_id,
        content=content,
        parent_comment_id=parent_comment_id,
        is_ai_generated=False,
        user_id=current_user.id
    )
    db.session.add(comment)
    db.session.commit()

    return jsonify({"message": "Comment submitted successfully"})

# API Endpoint: Vote on post
@app.route('/api/votes/posts', methods=['POST'])
@login_required
def api_vote_post():
    data = request.get_json()
    post_id = data.get('post_id')
    vote_type = data.get('vote_type')

    post = Post.query.get(post_id)
    if not post:
        return jsonify({"message": "Post not found"}), 404

    if vote_type == 'upvote':
        post.upvotes += 1
    elif vote_type == 'downvote':
        post.downvotes += 1
    else:
        return jsonify({"message": "Invalid vote type"}), 400

    db.session.commit()
    return jsonify({"message": "Vote recorded"})

# API Endpoint: Vote on comment
@app.route('/api/votes/comments', methods=['POST'])
@login_required
def api_vote_comment():
    data = request.get_json()
    comment_id = data.get('comment_id')
    vote_type = data.get('vote_type')

    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({"message": "Comment not found"}), 404

    if vote_type == 'upvote':
        comment.upvotes += 1
    elif vote_type == 'downvote':
        comment.downvotes += 1
    else:
        return jsonify({"message": "Invalid vote type"}), 400

    db.session.commit()
    return jsonify({"message": "Vote recorded"})

# Search Subllmits
@app.route('/api/subllmits', methods=['GET'])
def api_search_subllmits():
    query = request.args.get('query', '')
    subllmits = Subllmit.query.filter(Subllmit.name.ilike(f'%{query}%')).all()

    return jsonify([{
        "id": subllmit.id,
        "name": subllmit.name
    } for subllmit in subllmits])

# Route to view a specific subllmit
@app.route('/r/<subllmit_name>')
def view_subllmit(subllmit_name):
    subllmit = Subllmit.query.filter_by(name=subllmit_name).first()
    if not subllmit:
        flash('Subllmit not found', 'danger')
        return redirect(url_for('index'))
    return render_template('index.html', subllmit_name=subllmit_name)

# API Endpoint: Get all subllmits (for initial load)
@app.route('/api/subllmits/all', methods=['GET'])
def api_get_all_subllmits():
    subllmits = Subllmit.query.all()
    return jsonify([{
        "id": subllmit.id,
        "name": subllmit.name
    } for subllmit in subllmits])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Check if there are any subllmits, if not, create some default ones
        if Subllmit.query.count() == 0:
            default_subllmits = ['announcements', 'general', 'tech', 'news']
            for name in default_subllmits:
                db.session.add(Subllmit(name=name))
            db.session.commit()
        
        # Optionally, add some sample posts if the database is empty
        if Post.query.count() == 0:
            sample_post = Post(
                group_name='general',
                title='Welcome to LLMit',
                content='This is a sample post to get you started!',
                is_ai_generated=False
            )
            db.session.add(sample_post)
            db.session.commit()
    
    app.run(debug=True)
