### introduction
*as a voracious and morally apathetic silicon valley works tirelessly to
automate the working-class creative out of existence, Web Corp® understands
that it cannot simply rest on its laurels. the looming spectre of artificial
intelligence is knocking on our door, and shareholders have never been so
bullish! standing now on the precipice of untold profit, we present: wuckbot.*

**wuckbot provides a streamlined way to collaborate on work-in-progress songs
(WIPs), with explicit focus on reducing clutter, improving archival, and
maintaining focus.** basically, you buy into the way wuckbot organizes things,
and, in return, wuckbot organizes things.

throughout this document, we're gonna go through the problems wuckbot was built
to solve and the way wuckbot tries to solve them. to do this, we'll give
examples with some made up webcagers; we'll call them *quikslvr*, *4kmirage*,
and *gabby*. **if you just want to get started, see the [usage](USAGE.md).**
### where we are now
> quikslvr makes a WIP and shares it in `#open-tracks`. 4kmirage likes it and
> replies with a verse. later, in vc, quikslvr and 4kmirage are working out
> the production together, when gabby joins and offers to add a verse. they
> share their files through `#cage-vc-chat`, but gabby doesn't finish his verse
> until after the call ends, so he follows up by sending it in `#music-chat`.
> they send it to `#feedback`, where someone chips in a synth layer or two.

though the current state of things *can* get songs done, it's a nightmare for
organization. it's not uncommon for one song's production to happen over 3-4
channels. during production, that makes questions that *should* be easy very
difficult for anyone not already involved:
- what does the current version of the song sound like?
- can i borrow quikslvr's vocals? i want to try something.
- how long has it been since anyone's worked on this song?

collaboration becomes much more difficult when all our songs are hidden in
plain sight! let's watch our heroes navigate this issue:
### one song, one channel
> sick of the chaos, quikslvr comes up with an idea: each work-in-progress
> should get its own channel. they still use `#open-tracks`, but if a song gets
> any more work, it is placed in its own channel until it's finished. quikslvr
> instructs the rest of the band to follow suit.  
> the band agrees, and within two months, there are ten WIP channels with songs
> in various stages of completion. some are close to done, and others are close
> to abandoned.

certainly, one song per channel *feels* a lot more organized. and it solves a
few of our old problems--it's definitely easier to find stems and track
progress. it's also much easier to find the current state of a song (though it
may get lost in a sea of stems and messages).

but it's not our silver bullet--there are some *serious* drawbacks. the most
serious is probably clutter: *ten* channels? if each person is only on 1-2
songs, that means 80-90% of their channel list is a very low priority to them.
and keeping up-to-date with active projects has gotten *worse*, not
better--instead of peeking at `#music-chat` every once in a while, you have to
scrub through eight different channels? it all seems a bit... cluttered.

### roles and private channels
> gabby has long-since given up on keeping an attentive eye on the double-digit
> number of song channels that occupy the server. he yearns for the days of
> email newsletters, where he signed up for only the information relevant to
> himself, and only that information was delivered.  
> in a moment of sheer desperation, he sets all the song channels to private,
> make a role for each WIP's collaborators, and allows each role to access its own WIP channel.
> in the pinned messages of `#the-cage`, he inscribes his new doctrine:
> `@everyone if you need access to a song, add yourself to the role for it.`
> at long last, the ringing in his ears begins to clear.

as a stay-at-home mom's third-favorite wooden box sign once read: "bless this
mess." clutter can be a lot to process, but when you have a lot of stuff to
churn through, hiding it from view can hurt more than it helps. how are we
supposed to call ourselves a band when we don't even know our own songs?

let's not write this idea off quite yet, though. it might be a bit overkill,
but it's less awful than you might think.
### updates
> the server's on the brink of total death, now--who would've thought blocking
> everyone's access to each other's ideas would kill our productivity? as
> gabby takes some time to decompress, 4kmirage, WIP in hand and hungry for
> validation, makes a new channel.  
> next to `#open-tracks` sits `#updates`, a channel for sharing progress
> updates. any time significant progress has been made on a song, it gets sent
> to `#updates` for praise and feedback. if an update inspires a new
> collaborator, they can always join the WIP channel!

a channel to aggregate updates solves a lot of the problems that
one-channel-per-song creates. finding the current status of each song is
simple, since it's always in `#updates`! and though making song channels
private obviously has its flaws (*someone should really make that a thing you
can toggle...*), a lot of the issues with visibility are solved just by putting
updates somewhere everyone can access. really, there's only one or two problems
i can spot with this...
### archival
> after a lot of hard work, gabby, 4kmirage, and quikslvr package up their
> webcage song and release it. it's a great day for webcage fans, who finally
> get to hear their three favorite cagers on one track! when they return,
> though, they have an issue. what do they do with the channel?  
> they're not the only ones with this problem--though *they* got their song to
> the finish line, many others weren't as lucky. come to think of it, there's a
> few songs on here that are never gonna see the light of day.

reducing clutter is important for keeping creativity from becoming a chore. but
this is a pretty rough spot, right? we definitely don't want to accrue dead WIP
channels. but unlike our old system, the story of a song *lives* in this one
channel. its stems, its ideas, any alternate cuts--there's good reason to keep
it all around, even if we don't plan on viewing it all that often.

> instead of deleting the channel, gabby, always quick to make a private role,
> has a plan: he puts the channel in a category accessible only to those with
> a role called `view archive`. the channel still exists, but it's hidden out
> of sight!

the concept of 'archival' was taught to early programmers by the TLC show
"The Long Island Medium". in the show, the dead don't *actually* die--they're
still viewable to those with a special role. it's no different here! if we're
all big enough nerds to pay for discord nitro and soundcloud pro, i see no
reason to try and save our digital overlords' hard drive space.
### sketches
> after their song, gabby, quikslvr, and 4kmirage are hanging out in vc,
> patting themselves on the back for how smart their new system is. "hey," says
> quikslvr, "let's start something new!" they open up the daw and start
> cooking. when they finally have a stem or two to send to gabby and 4kmirage,
> a thought escapes their lips... "it's a bit too early to call this a WIP,
> right?"

WIPs are good for working asynchronously--one person makes an open, the next
adds a verse, etc. but when starting a song, they're a uniquely bad tool. for
one, they're hidden entirely from view! early in a song's development, we want
as many ears on it as possible. we could maybe send an update, but even updates
don't make much sense early on--the song might sound completely different in 20
minutes.

> gabby and 4kmirage agree--this *shouldn't* be a WIP yet. instead of making a
> private channel, they keep it public. they decide that they'll work on it for
> now, and if they like it, they'll turn it into a full WIP. otherwise, they'll
> archive the files somewhere and delete the channel. for now, they call it
> a "sketch".

this setup--one song per private channel, with special roles, updates,
archival, and sketches--*this* is the organizational setup that wuckbot seeks
to maintain. automation removes a lot of the tedium, here: making a WIP from
an open track takes two clicks, making a sketch takes one click, and making an
update (which includes uploading to soundcloud) is all handled when you add a
special reaction to a file.

see [usage](USAGE.md) for a tutorial on how to use the bot.
