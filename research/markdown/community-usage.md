# CoWriter applet usage evidence

Research resumed 2026-11-21. Question: would using AlphaWord's single CoWriter
companion lookup displace a feature that people use?

## What this search can establish

Three distinct firsthand personal/household reports were located in public
sources, plus one school deployment report. These are historical reports, not a
count of active users in 2026. Only one household report and the school deployment
explicitly identify Neo2; the other two concern earlier AlphaSmart hardware.
Do not add school students to the personal-report count or assume anonymous
comments represent distinct people.

| Source | Evidence | Count/category |
| --- | --- | --- |
| [Hand to Mouth, 2009-08-08](https://hand2mouth.wordpress.com/2009/08/08/alphasmart-neo-dvorak-accessible-communication/) | Author describes using a hand-me-down AlphaSmart 3000, one-handed Dvorak and preinstalled Co:Writer to reduce movement when typing with a stick. The page repeats its article text; count once. | One historical personal user; not a Neo owner |
| [LD Online, comment dated 2002-07-03](https://www.ldonline.org/forum/teaching-students-ld-and-adhd/alphasmart-what-it) | Parent reports daughter uses an AlphaSmart with the CoWriter applet, and discusses its visual-only limitations. Later comments repeat the same daughter's circumstances. | One historical household; do not count repeated anonymous comments separately |
| [Well-Trained Mind, Accommodations for struggling writers](https://forums.welltrainedmind.com/topic/455968-accommodations-for-struggling-writers/) | Search-indexed firsthand parent report explicitly describes son using AlphaSmart Neo2 with CoWriter after oral composition. | One historical household; index excerpt accessible, full thread fetch failed |
| [Joshua Jenkins / Yale Dyslexia](https://dyslexia.yale.edu/resources/educators/school-culture/a-charter-schools-journey-into-assistive-technology/) | Teacher describes actual NEO2 with Co:Writer classroom use, including text-to-speech. Narrative is set around the 2011–2012 school year; this is not the web crawl date. | One historical deployment; multiple students, no inferred user total |

The reports show actual accessibility uses. They do not establish current demand,
market share, or whether the Neo applet is still part of those users' routines.

## Reddit and other groups

No verified current firsthand r/alphasmart CoWriter applet user was identified
in this search. This is **not evidence that the number is zero**. Queries covered
CoWriter, Co:Writer and co-writer, combined with AlphaSmart/Neo, and Reddit-specific
site filters. Indexed results were sparse or irrelevant; direct Reddit subreddit
search and a candidate thread could not be retrieved. No logged-in/private group
search was available. Modern desktop/cloud CoWriter use, product descriptions,
sales listings and generic recommendations were excluded from actual-user counts.

A [Flickr Neo storage thread](https://www.flickr.com/groups/39436080@N00/discuss/72157676693647000/)
contains dougwalkabout's recollection that one Neo had storage reserved by CoWriter.
That establishes an installed-applet/ownership mention, not demonstrated prediction
use, and is excluded from the three firsthand-use reports above. Other LD Online
parent threads may duplicate the same family; they are not added without identity
or contextual evidence sufficient to distinguish them.

## Consequence for the integration design

Using the CoWriter name prefix is viable as an explicitly selected compatibility
mode on devices without genuine CoWriter. It is not transparent coexistence:
AlphaWord caches a single matching companion, and native editor rendering also
looks up CoWriter for its status indicator. Hiding our applet does not remove the
name collision. Installation order should not become an accidental feature switch.

A shipping installer should detect genuine CoWriter (including known ID A101),
explain the conflict and preserve a standalone viewer route. Coexisting through a
broker would need deterministic lookup selection, forwarding of lifecycle and
character/key/status messages, dictionary/prediction tests and screen ownership
rules. None of that has been implemented or certified here. Reimplementing all
prediction functionality is not required to deliver a standalone Markdown viewer.
