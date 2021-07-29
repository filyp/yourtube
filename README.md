# YourTube

![build](https://github.com/filyp/YourTube/actions/workflows/build.yml/badge.svg)
[![Downloads](https://pepy.tech/badge/yourtube)](https://pepy.tech/project/yourtube)
[![CodeFactor](https://www.codefactor.io/repository/github/filyp/yourtube/badge)](https://www.codefactor.io/repository/github/filyp/yourtube)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


Better youtube recommendations

- [x] More autonomy when choosing what to watch
- [x] Completely private
- [ ] Less clickbait
- [ ] Recommendations for two or more people
- [ ] Highly customizable
- [ ] Freetube integration
- [ ] Sharing and browsing information bubbles


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