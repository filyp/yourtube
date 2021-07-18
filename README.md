# YourTube

Better youtube recommendations

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

It will collect recommendations from all the videos in your playlists which can take a while.

Now, you can explore your recommendations by running:
```
yourtube
```