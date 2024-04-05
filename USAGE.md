# usage
the following document describes how to use wuckbot. it assumes you know the
terms `WIP channel`, `sketch`, `update`, and `archive` as defined in the
[readme](README.md).
### make a WIP channel
- from a track in `#open-tracks`:
	- click the `...` (on mobile, long-press)
	- select `Apps`, then `WIPify`
	- a dialog will appear, asking for a title and current progress
- from an existing sketch:
	- type `/wipify`
	- a dialog will appear, asking for a title and current progress
### make a sketch
- click the `New Sketch` button in `#sketchpad`
### join a WIP channel
- add yourself with `/wips join <WIP name>`
- add someone else to a WIP with `/wip join <username>` inside the WIP channel
- view all WIPs with `/wips view`, which provides an option to join each WIP.
- when a WIP or update is created, a button is also sent to join the WIP.
### leave a WIP channel
- `/wip leave` inside the WIP channel
- you can also remove someone else with `/wip leave <username>`
### send an update
- when you send a file, the bot will react with a bell.
	- ring the bell to send an update
### view all WIPs
- `/wips viewall` will let you access all WIPs, even ones you're not joined to
	- use this command again to leave this view
- show a list of all WIPs with `/wips view`
### give credit in a WIP
- to credit a vocalist, use `/wip credit vocalist <username>`
	- use this command again to remove credit
- to credit a producer, use `/wip credit producer <username>`
	- use this command again to remove credit
### archival
- to archive a WIP or sketch, use `/archive`
- to view all archived channels, use `/viewarchive`
	- use this command again to leave this view
