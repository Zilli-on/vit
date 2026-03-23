# Same project, different people

Vit shares the **edit** (timeline, color, sound). It does **not** upload your video files—share footage the way you already do (drive, Dropbox, server).

You need **Vit installed**, **Git installed**, and (for Resolve) **`vit install-resolve`** once, then restart Resolve. If any command is “not found,” finish install from the main **README** first.

---

## Before the host runs setup

1. On **GitHub** (or GitLab, etc.), create a **new empty repository** (no README, no license).  
2. Copy the **HTTPS clone URL** (looks like `https://github.com/yourname/your-repo.git`).

---

## Person who starts the project (once)

1. Open **Terminal**.
2. Go where you want the folder, for example:  
   `cd ~/Documents`
3. Create the Vit project (pick your own folder name):  
   `vit init my-project`  
   Then enter it:  
   `cd my-project`
4. In **DaVinci Resolve**: open or create a project and a timeline.  
5. **Workspace → Scripts** → run a Vit item (e.g. **Save Version**). If a window asks for a folder, choose **`my-project`** (the folder that contains `.vit`).  
   - If no window appears, quit Resolve, then in Terminal run:  
     `export VIT_PROJECT_DIR="$HOME/Documents/my-project"`  
     (change the path if yours is different), then open Resolve again and retry.
6. Back in **Terminal** (still inside `my-project`):  
   `vit collab setup`  
   Paste the **empty repo URL** when asked. Sign in to GitHub if Terminal asks.  
7. Copy the **`vit clone …`** line Terminal prints and send it to everyone.

---

## Everyone else joining (once)

1. Open **Terminal**.
2. Go where you want the project folder to appear, for example:  
   `cd ~/Documents`
3. Paste the full command you were sent, for example:  
   `vit clone https://github.com/yourname/your-repo.git`  
   Terminal creates a **new folder** (usually named like the repo).
4. Go into that folder:  
   `cd your-repo`  
   (use the real folder name Terminal showed after clone.)
5. Load the latest saved edit into the project files:  
   `vit checkout main`  
6. Copy your team’s **footage** onto your machine (same files, any path is OK if you relink).
7. **DaVinci Resolve**: open **your** Resolve project (or create one with a timeline).  
8. **Workspace → Scripts** → run Vit’s **Switch Branch / Restore** (or the item that restores the timeline). When asked for a folder, pick the **cloned** folder from step 4.  
9. **Relink** offline clips in Resolve if you see red media.  
10. Create your own line of work (use a name your lead agrees on):  
    `vit branch your-name`

---

## Every work session

1. **Terminal** → `cd` into your vit project folder (same folder that has `.vit` inside).  
2. `vit pull`  
3. **Resolve** → **Workspace → Scripts** → **Switch Branch / Restore** (or restore) on **your** branch so the timeline matches what you just pulled.  
4. Edit as usual.  
5. **Workspace → Scripts** → **Save Version** when you want to record this state.  
6. **Terminal** → `vit push`

Always run `vit pull` / `vit push` from **inside** the project folder, not from your home folder.

---

## Putting two people’s work together (lead / editor)

Do this from the **project folder** in Terminal.

1. `vit pull`  
2. `vit checkout main`  
   (or whatever branch everyone merges **into**—your team should agree on the name.)  
3. `vit merge other-persons-branch`  
   Use the exact branch name they used (no spaces in the name is easiest).  
4. `vit push`  
5. In **Resolve**, run **Switch Branch / Restore** on that same branch so you **see** the merged timeline.

Tell everyone else to `vit pull` and restore in Resolve when they’re ready to pick up the merge.

---

## If something goes wrong

| Problem | What to try |
|--------|----------------|
| Vit says “not a project” | `cd` into the folder that contains `.vit`, then run the command again. |
| Resolve says “No vit project” | Run a Vit script and pick the correct folder, or set `VIT_PROJECT_DIR` to that folder and restart Resolve. |
| Clone worked but timeline looks wrong | In Terminal: `vit checkout main`. In Resolve: **Switch Branch / Restore**. |
| `vit collab setup` push failed | Create an **empty** repo on the host first, then try again; check you’re logged into GitHub in Terminal. |

More detail: main **README** or whoever installed Vit for your team.
