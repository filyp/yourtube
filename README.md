# YourTube

![build](https://github.com/filyp/YourTube/actions/workflows/build.yml/badge.svg)
[![Downloads](https://pepy.tech/badge/yourtube)](https://pepy.tech/project/yourtube)
[![CodeFactor](https://www.codefactor.io/repository/github/filyp/yourtube/badge)](https://www.codefactor.io/repository/github/filyp/yourtube)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


Better youtube recommendations

- [x] More autonomy when choosing what to watch
- [x] Complxtely private
- [x] Very customizable
- [ ] Less clickbait
- [ ] Recommendations for two or more people
- [ ] Freetube integration
- [ ] Sharing and browsing information bubbles

You can play with the demo here: [http://193.19.165.86:8866](http://193.19.165.86:8866). It's meant only to show what it can do. To have personalized recommendations, you have to install it.


## Installation

```
pip install yourtube
mkdir ~/.yourtube
```

Now export your data from youtube with these steps (sadly this cannot be automated):
1. Login to your YouTube account
2. Click on your profile picture in the top right corner of the web page
3. Make sure your preferred language is English
4. Click on "Your data in YouTube" in the displayed drop down
5. Click on "More" in the "Your YouTube dashboard" card
6. Click on "Download YouTube data"
7. Under "Create a New Export", make sure "YouTube and YouTube Music" is selected
8. Click "Next step"
9. Select your preferred method of delivery (Email, Dropbox, etc.) and click on "Create Export"
10. Download the .zip file
11. Extract it into `~/.yourtube`, so that you have the structure: `~/.yourtube/Takeout/...`

Now run:
```
yourtube-scrape
```

It will collect recommendations from the videos in your playlists and from your liked videos, which can take a few hours.

For best experience also run:
```
yourtube-scrape-watched
```

Now, you can explore your recommendations by running:
```
yourtube
```

# Customization

All the parameters can be set in URL query like this: 

http://localhost:8866/?num_of_groups=3&videos_in_group=4&clustering_balance=1.4&recommendation_cutoff=0.7&column_width=1000

or for the demo:

http://193.19.165.86:8866/?num_of_groups=3&videos_in_group=4&clustering_balance=1.4&recommendation_cutoff=0.7&column_width=1000

`recommendation_cutoff` must be between 0 and 1; the higher, the more predictable the recommendations; low values are good for content exploration

`clustering_balance` must be greater or equal to 1, generally values between 1.3 and 2 are fine