from yandex_music import Client

client = Client('token').init()
# tracks = core.users_likes_tracks()
# tracks = core.tracks(['56922700:8478451']) #trackId:albumId

# print(tracks)
client.users_likes_tracks()[0].fetch_track().download('example.mp3')
# core.users_likes_tracks()[0].fetch_track().download_cover('example.jpeg')
# albums = core.albums()
# print(albums)