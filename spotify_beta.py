import os 
from flask import Flask, session, request, redirect, url_for, render_template
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
import matplotlib.pyplot as plt

app= Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = os.urandom(64)

client_id='14d584ba4cd0465894be76a1321e3311'
client_secret='579ab22ed5964b53a0ef81897db289a9'
redirect_uri= 'http://localhost:5000/callback'
scope='playlist-read-private, user-library-read'

cache_handler = FlaskSessionCacheHandler(session)

#How we authenticate with the spotify web API
sp_oauth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope,
    cache_handler=cache_handler,
    show_dialog=True 
)

# This allows us to interact with the web API
sp=Spotify(auth_manager=sp_oauth)

def generate_bar_chart(data, labels, title, xlabel, ylabel, filename):
    #Generate a bar chart using Matplotlib and save it to the static folder.
    
    plt.figure(figsize=(14, 7))
    plt.bar(labels, data, color='#1DB954')
    plt.title(title, fontsize=16)
    plt.xlabel(xlabel, fontsize=12)
    plt.ylabel(ylabel, fontsize=12)
    plt.xticks(rotation=90, fontsize=8)
    plt.tight_layout()
    chart_path = os.path.join(app.static_folder, filename)
    plt.savefig(chart_path)
    plt.close()
    return filename

def generate_genre_pie_chart(genres_count):
    labels=list(genres_count.keys())
    sizes=list(genres_count.values())

    #List of hex codes for the spotify-themed color palette
    spotify_colors=[
        '#1DB954',  #Spotify Green
        '#1ED760',  #Light Green
        '#535353',  #Dark Gray
        '#B3B3B3',  #Light Gray
        '#121212',  #Black
        '#FFD700',  #Gold
    ]

    # If there are more 6 genres (6 colors available), cycle different colors
    colors=spotify_colors*(len(labels)//len(spotify_colors)+1)

    plt.figure(figsize=(9,9))
    plt.pie(sizes, 
            labels=labels, 
            autopct='%1.1f%%', 
            startangle=140, 
            colors=colors[:len(labels)],
            wedgeprops={'edgecolor':'white'}
    )
    plt.title('Genre Breakdown', fontsize=16)

    #Save the chart
    chart_path=os.path.join(app.static_folder,'genres_chart.png')
    plt.savefig(chart_path)
    plt.close()
    
    return 'genres_chart.png'


@app.route('/')
def home():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()): #If not logged in
        auth_url = sp_oauth.get_authorize_url() #Takes user to spotify log-in page
        return redirect(auth_url) #Redirecting to the URL
    return redirect(url_for('get_playlists'))

#Callback endpoint - no idea what this means
@app.route('/callback')
def callback():
    sp_oauth.get_access_token(request.args['code'])
    return redirect(url_for('get_playlists'))

#Get user's playlists
@app.route('/get_playlists')
def get_playlists():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()): #Makes sure the log-in token is still valid
        auth_url = sp_oauth.get_authorize_url() #Takes user to spotify log-in page
        return redirect(auth_url) #Redirecting to the URL
  
    # Creates an empty list to put the dictionaries in
    playlists=[]
    results=sp.current_user_playlists() # Retrieves all of the playlists

    #If 'items' does not exist, default to an empty list to avoid errors
    for playlist in results.get('items',[]):
        if playlist: # Checks if the playlist is not None
            # Append a dictionary with the playlist details to the playlist list
            playlists.append({
                'name': playlist.get('name','Unknown'), #Get the playlist name or 'Unknown' if it doesn't exist
                'id': playlist.get('id','Unknown'), #Get the playlist ID or 'Unknown' if it doesn't exist
                #Safely access the 'tracks' dictionary and get the total number of tracks, default to 0 if missing
                'tracks': playlist.get('tracks',{}).get('total',0)
            }) #Appends each dictionary to the playlist list

    # Takes the playlist variable to the playlist.html file
    return render_template('playlists.html', playlists=playlists) 

@app.route('/playlist/<playlist_id>')
def get_playlist_tracks(playlist_id):
    if not sp_oauth.validate_token(cache_handler.get_cached_token()): #Makes sure the log-in token is still valid
        auth_url = sp_oauth.get_authorize_url() #Takes user to spotify log-in page
        return redirect(auth_url) #Redirecting to the URL

    tracks = [] # Emplty list that will be filled with dictionaries of songs
    popularity_scores = [] #Store popularity scores
    track_durations = [] #Store duration in minutes
    track_names=[] #Store track names
    genres_count={} #Store genres and their counts

    results=sp.playlist_tracks(playlist_id, limit=100) #Gets the first 100 songs in a playlist 
    items=results.get('items',[])
    
    for item in items: # Iterates through the list?(dictionary?) of songs
        track = item.get('track')
        if track: #Ensure track is not None
            track_name=track['name']
            # Appends the dictionary of a song into lists 
            tracks.append({
                'name': track['name'],
                'artist': ','.join([artist['name'] for artist in track['artists']]),
                'duration':round(track['duration_ms']/60000, 2), # Converts ms to minutes
                'popularity': track['popularity']
            })
            # Collect data for charts
            popularity_scores.append(track['popularity'])
            track_durations.append(round(track['duration_ms']/60000, 2)) #Converts ms to minutes
            track_names.append(track_name)

            #Fetch artist genres
            artist_id=track['artists'][0]['id'] #Use the main artist
            artist_data=sp.artist(artist_id)
            artist_genres=artist_data.get('genres',[])

            #Update genre counts
            for genre in artist_genres:
                genres_count[genre]=genres_count.get(genre,0)+1
    
    genres_chart=generate_genre_pie_chart(genres_count)

    popularity_chart=generate_bar_chart(
        data=popularity_scores,
        labels=track_names,
        title="Popularity Distribution",
        xlabel="Tracks",
        ylabel="Popularity",
        filename="popularity_chart.png"
            )

    length_chart=generate_bar_chart(
        data=track_durations,
        labels=track_names,
        title="Track Length Distribution",
        xlabel="Tracks",
        ylabel="Duration (minutes)",
        filename="length_chart.png"
        )
    return render_template('tracks.html', 
                           tracks=tracks,
                           popularity_chart='popularity_chart.png',
                           length_chart='length_chart.png',
                           genres_chart='genres_chart.png')    

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)