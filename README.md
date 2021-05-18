# Freshbot
Starcraft 2 AI
The basic goal with this project is to learn coding in Python as well as
working with APIs while working with a game that I am very familiar with

Terrantestbot is a basic Terran that makes marines and medivacs and then pushes
into the enemy base when a certain number of marines are available.

Currently refactoring my old code from the 
[Old SC2 Library](https://github.com/Dentosal/python-sc2) into the 
[Updated SC2 Library](https://github.com/BurnySc2/python-sc2).

The next challenge is figuring out how to get an upgrade started (Stimpack).
Once I figure this out I plan on adding +attack and +armor upgrades to it as well.
The final bot will just mass marines and medivacs with upgrades and
possible drop harass if I feel like working on Terran more.

Freshbot will be an advanced Zerg and my main focus

Plan is for (in order of importance)
 - MAXIMUM creep spread
 - some form of early scout and defense
 - Hydra/Ling/Bane or Roach/Ravager builds based on scouted info(random if none)

## Maps
Official Blizzard map downloads are available from [Blizzard/s2client-proto](https://github.com/Blizzard/s2client-proto#downloads).
Extract these maps into their respective subdirectories in the SC2 maps directory.

e.g. `install-dir/Maps/Ladder2017Season1/`

### Bot ladder maps
Maps that are run on the [SC2 AI Ladder](http://sc2ai.net/) and [SC2 AI Arena](https://aiarena.net/) can be downloaded from the [sc2ai wiki](http://wiki.sc2ai.net/Ladder_Maps) and the [aiarena wiki](https://aiarena.net/wiki/bot-development/getting-started/#wiki-toc-maps).
Extract these maps into the root of the SC2 maps directory (otherwise ladder replays won't work).

e.g. `install-dir/Maps/AcropolisLE.SC2Map`
