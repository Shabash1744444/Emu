# CP-170 — PRE AI-OWNED BODY / USER-WORLD BOUNDARY

Date: 2026-10-07
Parent: CP-169 stable live chat GREEN
Status: PRE

User correction:
The user should not puppet C4's avatar with buttons such as "wave", "take" or "place". The organism owns its body.

Target ownership model:
- C4 owns avatar motor decisions.
- Android host owns physical execution and receipts.
- User may interact with the environment and with C4 as another agent (call, touch, present sources), but may not issue C4 motor actions directly.
- Sandbox task issuance may challenge C4, but task completion must happen through C4 ACTION_REQUEST -> host execution -> ACTION_RECEIPT.

UI repair:
- remove "Помахать" and direct body/object puppeteering controls from Home;
- remove user-side GRASP/RELEASE/LOOK controls which masquerade as C4 acts;
- keep avatar touch as USER->C4 sensory contact;
- keep "Позвать" as USER_WORLD social/environment event;
- add visible autonomy/motor status and recent C4 action;
- allow only C4 ACTION_REQUEST to animate/modify C4 body state.

Host motor expansion:
- support non-object motor gestures (WAVE, NOD, LOOK_AROUND, STEP_LEFT, STEP_RIGHT, IDLE) with verified sandbox receipts;
- preserve ACTION_REQUEST != VERIFIED_OUTCOME;
- reject unsupported motor verbs explicitly.

No cognitive law changes and no fabricated C4 actions.
