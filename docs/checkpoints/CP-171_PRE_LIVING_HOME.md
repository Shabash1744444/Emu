# CP-171 — PRE LIVING HOME VISUAL PASS

Date: 2026-10-07
Parent: CP-170 AI-owned body GREEN
Status: PRE

Reference direction from user:
- premium, dense, cinematic "living AI world" feeling;
- Home as the organism's place, not a debug scene;
- visible thoughts/initiative, world/library/learning surfaces;
- strong visual hierarchy and polish;
- chat remains the primary interaction surface.

Constraints:
- do not fabricate emotions, XP, curiosity, health or knowledge scores;
- every status shown as "real" must derive from runtime/app state;
- C4 owns avatar motor actions;
- user remains an external actor;
- no hidden semantic shortcuts.

Regression found before visual work:
Several collection selector calls in index.html had regressed from $$() to $(), which could crash WebView initialization. Repair this first and strengthen CI.

Target release:
0.51-living-home
