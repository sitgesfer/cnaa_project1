import logging
import os
import sqlite3
import sys

from flask import Flask, json, render_template, request, url_for, redirect, flash, has_request_context, session
from logging.config import dictConfig


# Function to get a database connection.
# This function connects to database with the name `database.db`
def get_db_connection():
    if 'dbstate' not in session:
        session['dbstate'] = ''
    if os.path.isfile('database.db') is False:
        session['dbstate'] = '\nDatabase is not initialized!'
        app.logger.error('Database is not initialized!')
        return False
    session['dbstate'] = 'Database initialized'
    connection = sqlite3.connect('database.db')
    connection.row_factory = sqlite3.Row
    if 'dbconnections' in session:
        session['dbconnections'] += 1
    else:
        session['dbconnections'] = 0
    return connection


# Function to get a post using its ID
def get_post(post_id):
    connection = get_db_connection()
    if connection is False:
        return False
    try:
        post = connection.execute('SELECT * FROM posts WHERE id = ?',
                                  (post_id,)).fetchone()
        connection.close()
        return post
    except Exception:
        app.logger.exception('An exception occurred when getting a post. %s', session['dbstate'])
        return False


# Function to get all posts
def get_all_posts():
    connection = get_db_connection()
    if connection is False:
        return False
    try:
        posts = connection.execute('SELECT * FROM posts').fetchall()
        connection.close()
        return posts
    except Exception as err:
        app.logger.exception('An exception occurred %s. %s', str(err), session['dbstate'])
        return False


# Function to get number of posts in database
def get_posts_count():
    connection = get_db_connection()
    if connection is False:
        return False
    try:
        posts = connection.execute('SELECT COUNT(*) AS count FROM posts').fetchone()
        connection.close()
        return posts['count']
    except Exception:
        app.logger.exception('An exception occurred when getting posts count. %s', session['dbstate'])
        return False


class RequestFormatter(logging.Formatter):
    def format(self, record):
        record.url = ''
        record.remote_addr = ''
        if has_request_context():
            record.url = request.url
            record.remote_addr = request.remote_addr
        return super().format(record)


dictConfig({
    'version': 1,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }
    },
    'handlers': {
        'wsgi': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stderr',
            'formatter': 'default'
        }
    },
    'root': {
        'level': os.getenv('LOGLEVEL', 'DEBUG'),
        'handlers': ['wsgi']
    }
})
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your secret key'


# Define the main route of the web application
@app.route('/')
def index():
    posts = get_all_posts()
    if posts is not False:
        app.logger.info('Home page was read!')
        return render_template('index.html', posts=posts)
    else:
        return 'Database error when trying to get posts'


# Define how each individual article is rendered 
# If the post ID is not found a 404 page is shown
@app.route('/<int:post_id>')
def post(post_id):
    post = get_post(post_id)
    if post is False:
        return 'Database error when trying to get post'
    if post is None:
        app.logger.error('Post with id %s does not exist', post_id)
        return render_template('404.html'), 404
    else:
        app.logger.info('Post with id %s with title "%s" was read!', post_id, post['title'])
        return render_template('post.html', post=post)


# Define the About Us page
@app.route('/about')
def about():
    app.logger.info('About page was read!')
    return render_template('about.html')


# Define the post creation functionality 
@app.route('/create', methods=('GET', 'POST'))
def create():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        if not title:
            flash('Title is required!')
        else:
            try:
                connection = get_db_connection()
                connection.execute('INSERT INTO posts (title, content) VALUES (?, ?)',
                                   (title, content))
                connection.commit()
                connection.close()
                app.logger.info('A new article with title "%s" was created', title)
                return redirect(url_for('index'))
            except Exception as err:
                app.logger.exception('An exception occurred %s. %s', str(err), session['dbstate'])
                return 'Database error when trying to insert post'

    return render_template('create.html')


@app.route('/healthz')
def healthcheck():
    connection = get_db_connection()
    count = get_posts_count()
    response = app.response_class(
        response=json.dumps({"result": "ERROR - unhealthy"}),
        status=500,
        mimetype='application/json'
    )
    if connection and count:
        app.logger.info('Healthz page showed a healthy status!')
        response = app.response_class(
            response=json.dumps({"result": "OK - healthy"}),
            status=200,
            mimetype='application/json'
        )
    else:
        app.logger.error('Healthz page showed an unhealthy status!')
    return response


@app.route('/metrics')
def metrics():
    count = get_posts_count()
    if 'dbconnections' in session:
        dbconnections = session['dbconnections']
    else:
        dbconnections = 0
    app.logger.info('Metrics were read, showing %s connections', dbconnections)
    response = app.response_class(
        response=json.dumps({"post_count": count, "db_connections": dbconnections}),
        status=200,
        mimetype='application/json'
    )
    return response


# start the application on port 3111
if __name__ == "__main__":
    formatter = RequestFormatter(
        '[%(asctime)s] %(remote_addr)s - %(url)s %(levelname)s in %(module)s: %(message)s'
    )

    LOGLEVEL = os.environ.get('LOGLEVEL', 'DEBUG').upper()

    root = logging.getLogger()
    errHandler = logging.StreamHandler(sys.stdout)
    errHandler.setFormatter(formatter)
    fileHandler = logging.FileHandler("app.log")
    fileHandler.setFormatter(formatter)
    root.addHandler(fileHandler)
    root.addHandler(errHandler)
    fileHandler.setLevel(LOGLEVEL)
    errHandler.setLevel(LOGLEVEL)
    app.run(host='0.0.0.0', port='3111')
