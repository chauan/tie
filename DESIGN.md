# Gateway radar: survival console

Design skill: [frontend-design](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md).

Purpose: inspect nearby dinosaurs and their condition quickly while playing The Isle. Preserve the calibrated map, replay timeline, 20-second collector, Telegram settings and existing account data.

Primary visual reference: the user's supplied dinosaur survival dashboard. Match its jungle/volcano header, bronze beveled frames, dark textured surfaces, condensed cream headings, amber controls, cyan map accents and illustrated dinosaur portraits. This reference supersedes the previous slate palette.

Palette: forest base `#0a100d`, raised surface `#141c17`, cream text `#f0eddb`, muted olive `#b8b8a4`, bronze/amber `#e2b565` and cyan `#79c7bf`. HP uses green (coral when low), Blood coral, and stamina amber. Keep labels and numerical values beside the colors.

Type: locally bundled Barlow Condensed Semibold for the brand, section titles, species names and compact status numbers. Segoe UI for interface text; Cascadia Mono / Consolas for coordinates and identifiers. The font supports Vietnamese. Bundle the OFL license and avoid remote fonts at runtime.

Layout: prioritize the island map beside the selected dinosaur, rather than making the user scroll through every setting first. Left-align the page. Put the selected target's vital meters before its dense metadata and target list. Collapse alert/account setup and AI density controls below the workspace. Use a horizontal, compact replay status row instead of oversized decorative number cards.

```
Gateway radar                        replay source / sync
compact status and replay timeline selection
map + movement indicators     | selected dinosaur
                              | HP / Blood / stamina
                              | Weight / food / speed / group
                              | search, filters, other targets
radar settings / teammates / Telegram (expand when needed)
AI density controls (expand when needed)
```

Data principles: distinguish observed Weight from HP-based estimates; do not claim kg until the unit is independently confirmed. Keep HP and Blood separate. Show each field at or before the chosen replay time. Unknown fields stay unknown. Decode only verified property signatures and supported widths. Label unknown ability/effect codes clearly; never invent names. Exclude Coelacanth spelling variants from both decoder output and legacy replay presentation.

Implementation: layer `web/survival.css` after the established layout styles. Use a roughly 2:1 map/inspector split on desktop, a two-column inspector/list on tablets and one column on phones. Bronze borders and corner strips are CSS; the icon sprite and subtle metal grain are native SVG. Generate background and portrait bitmap assets with the imagegen skill, then save them in `web/assets`. Use Allosaurus and Carnotaurus portraits only for their matching species; show a generic skull for other species. Do not imply the illustration is the individual's in-game appearance.

Interaction: retain replay selection, playback, history isolation, map gestures, measurement, following, export, account selection and Telegram configuration. Keep keyboard focus indicators, reduced motion support and honest missing-data states. Keep controls usable at 320 px. Map artwork and calibrated coordinates remain the functional geographic source; decorative background art never supplies map data.

Keyboard interaction: preserve focus on the same dinosaur when selecting a map marker or list row and when replay rendering refreshes it. Expose the SVG as an interactive group and the selected marker as a pressed button. Restore focus without changing the scroll position.

Asset origins, generation prompts and font license are documented in [SURVIVAL-ART.md](web/assets/SURVIVAL-ART.md).

Verification: real replay comparison against the previous decoder, schema/timeline isolation, exclusion variants, attribute signatures, group and movement units, unknown effect handling, keyboard/focus behavior, screenshots at desktop and 390/320 px, and existing Telegram rule regressions. Test notifications use mocked transport.
