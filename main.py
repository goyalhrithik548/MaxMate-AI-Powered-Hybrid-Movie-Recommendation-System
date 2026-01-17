import numpy as np
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import json
import pickle
import random
from pymongo import MongoClient
from bson.objectid import ObjectId
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key'

# --- DATABASE SETUP ---
client = MongoClient('mongodb://localhost:27017/')
db = client['content_recommender_db']
users_collection = db['users']

bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class User(UserMixin):
    def __init__(self, user_dict):
        self.id = str(user_dict['_id'])
        self.username = user_dict['username']
        self.password = user_dict['password']


@login_manager.user_loader
def load_user(user_id):
    try:
        user_data = users_collection.find_one({"_id": ObjectId(user_id)})
        if user_data: return User(user_data)
    except:
        return None
    return None


# --- LOAD DATA ---
data = pickle.load(open('Artifacts/movies_list.pkl', 'rb'))
similarity = pickle.load(open('Artifacts/similarity_score.pkl', 'rb'))
qualified_data = pickle.load(open('Artifacts/qualified_movies.pkl', 'rb'))

try:
    if 'movie_id' in data.columns:
        full_data = data.merge(qualified_data[['movie_id', 'trending', 'all_time_fav']], on='movie_id', how='left')
        full_data['trending'] = full_data['trending'].fillna(0)
        full_data['all_time_fav'] = full_data['all_time_fav'].fillna(0)
    else:
        full_data = qualified_data
except:
    full_data = qualified_data


# --- HELPER FUNCTIONS ---
def rcmd(m):
    m = m.lower()
    titles_lower = data['title'].str.lower()
    if m not in titles_lower.values:
        return []
    else:
        i = titles_lower[titles_lower == m].index[0]
        lst = sorted(list(enumerate(similarity[i])), key=lambda x: x[1], reverse=True)[1:11]
        return [data['title'][x[0]] for x in lst]


def get_suggestions():
    return list(data['title'].str.capitalize())


def get_personalized_recs(seeds):
    # Get unique seeds and pick the last 5
    seeds = list(set(seeds))[-5:]
    final_recs = []
    seen_movies = set(seeds)

    for seed in seeds:
        recs = rcmd(seed)
        for r in recs:
            if r not in seen_movies:
                final_recs.append(r)
                seen_movies.add(r)

    random.shuffle(final_recs)
    return final_recs[:12]


# --- ROUTES ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if users_collection.find_one({'username': username}): return "User already exists!"
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        users_collection.insert_one({'username': username, 'password': hashed_password})
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_data = users_collection.find_one({'username': request.form['username']})
        if user_data and bcrypt.check_password_hash(user_data['password'], request.form['password']):
            login_user(User(user_data))
            return redirect(url_for('home'))
        return "Invalid credentials"
    return render_template('login.html')


@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop('session_interests', None)  # Clear session history on logout
    return redirect(url_for('login'))


# --- Import your local brain ---
# Make sure local_llm.py is in the same folder
from max_llm import get_local_response


@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_msg = request.json['message']

        # Call the local function
        bot_reply = get_local_response(user_msg)

        return jsonify({'response': bot_reply})

    except Exception as e:
        print(f"Chat Error: {e}")
        return jsonify({'response': "I'm thinking too hard... try again!"})

@app.route("/")
@app.route("/home")
@login_required
def home():
    suggestions = get_suggestions()

    # 1. Hero Movie
    try:
        hero_row = full_data[full_data['trending'] == 1].iloc[0]
        hero_id = int(hero_row['movie_id'])
        overview = hero_row['overview'] if 'overview' in hero_row else ""
        hero_movie = {'title': hero_row['title'], 'overview': overview, 'id': hero_id}
    except:
        hero_movie = {'title': "Welcome", 'overview': "", 'id': 550}

    # 2. Trending & Classics
    trending_movies = full_data[full_data['trending'] == 1].head(15)[['title', 'movie_id']].rename(
        columns={'movie_id': 'id'}).to_dict(orient='records')
    classic_movies = full_data[full_data['all_time_fav'] == 1].head(15)[['title', 'movie_id']].rename(
        columns={'movie_id': 'id'}).to_dict(orient='records')

    # 3. PERSONALIZED RECOMMENDATIONS
    seeds = session.get('session_interests', [])

    # Add Likes/Saves from DB
    user_data = users_collection.find_one({"_id": ObjectId(current_user.id)})
    if user_data:
        for m in user_data.get('liked_movies', []):
            seeds.append(m['title'])
        for m in user_data.get('saved_movies', []):
            seeds.append(m['title'])

    personalized_titles = get_personalized_recs(seeds)

    recommended_movies = []
    for title in personalized_titles:
        row = full_data[full_data['title'].str.lower() == title.lower()]
        if not row.empty:
            recommended_movies.append({
                'title': row.iloc[0]['title'],
                'id': int(row.iloc[0]['movie_id'])
            })

    return render_template('home.html',
                           suggestions=suggestions, hero=hero_movie,
                           trending=trending_movies, classics=classic_movies,
                           recommendations=recommended_movies)


@app.route('/log_interaction', methods=['POST'])
def log_interaction():
    try:
        data = request.get_json()
        title = data['title']
        duration = data['duration']

        # If user stays > 15 seconds, interest is captured
        if duration > 15:
            if 'session_interests' not in session:
                session['session_interests'] = []

            current_interests = session['session_interests']
            if title not in current_interests:
                current_interests.append(title)
                session['session_interests'] = current_interests
                session.modified = True

        return jsonify({'status': 'success'})
    except:
        return jsonify({'status': 'error'})


@app.route("/similarity", methods=["POST"])
def similarity_check():
    movie = request.form['name']
    rc = rcmd(movie)
    if type(rc) == type('string'):
        return rc
    else:
        return "---".join(rc)


@app.route("/recommend", methods=["POST"])
def recommend():
    try:
        movie_id = request.form['movie_id']
        title = request.form['title']
        poster = request.form['poster']
        genres = request.form['genres']
        overview = request.form['overview']
        vote_average = request.form['rating']
        vote_count = request.form['vote_count']
        release_date = request.form['release_date']
        runtime = request.form['runtime']
        status = request.form['status']

        rec_movies = json.loads(request.form['rec_movies'])
        rec_posters = json.loads(request.form['rec_posters'])
        cast_names = json.loads(request.form['cast_names'])
        cast_ids = json.loads(request.form['cast_ids'])
        cast_chars = json.loads(request.form['cast_chars'])
        cast_profiles = json.loads(request.form['cast_profiles'])
        cast_bdays = json.loads(request.form['cast_bdays'])
        cast_bios = json.loads(request.form['cast_bios'])
        cast_places = json.loads(request.form['cast_places'])

        movie_cards = {rec_posters[i]: rec_movies[i] for i in range(len(rec_posters))}
        casts = {cast_names[i]: [cast_ids[i], cast_chars[i], cast_profiles[i], cast_bdays[i], cast_places[i], cast_bios[i]] for i in range(len(cast_profiles))}

        # --- NEW LOGIC: Check if Liked/Saved ---
        user = users_collection.find_one({'_id': ObjectId(current_user.id)})
        liked_list = user.get('liked_movies', [])
        saved_list = user.get('saved_movies', [])

        # Check if current movie_id exists in lists (compare as strings to be safe)
        is_liked = any(str(m['id']) == str(movie_id) for m in liked_list)
        is_saved = any(str(m['id']) == str(movie_id) for m in saved_list)

        return render_template('recommend.html', movie_id=movie_id, title=title, poster=poster, overview=overview, vote_average=vote_average,
                            vote_count=vote_count, release_date=release_date, runtime=runtime, status=status,
                            genres=genres, movie_cards=movie_cards, casts=casts,
                            is_liked=is_liked, is_saved=is_saved) # Pass flags to HTML

    except Exception as e:
        print(f"Error: {e}")
        return "Error loading details"

@app.route('/toggle_action', methods=['POST'])
@login_required
def toggle_action():
    try:
        data = request.get_json()
        action = data['action']
        movie_data = {'id': data['movie_id'], 'title': data['title'], 'poster': data['poster']}
        user_id = ObjectId(current_user.id)
        user = users_collection.find_one({'_id': user_id})
        field = "liked_movies" if action == "like" else "saved_movies"
        current_list = user.get(field, [])

        exists = False
        for m in current_list:
            if str(m['id']) == str(movie_data['id']):
                exists = True
                break

        if exists:
            new_list = [m for m in current_list if str(m['id']) != str(movie_data['id'])]
            users_collection.update_one({'_id': user_id}, {'$set': {field: new_list}})
            status = "removed"
        else:
            users_collection.update_one({'_id': user_id}, {'$push': {field: movie_data}})
            status = "added"
        return jsonify({'status': 'success', 'action': status})
    except:
        return jsonify({'status': 'error'})


@app.route('/profile')
@login_required
def profile():
    user_data = users_collection.find_one({'_id': ObjectId(current_user.id)})
    return render_template('profile.html', username=user_data['username'],
                           liked_movies=user_data.get('liked_movies', []),
                           saved_movies=user_data.get('saved_movies', []))


if __name__ == '__main__':
    # debug=False prevents the console crash
    app.run(debug=False, host='0.0.0.0', port=5000)