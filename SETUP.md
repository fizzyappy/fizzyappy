# Setting up the pond & lab

## 1. Create the profile repo
GitHub → **New repository** → name it exactly **`fizzyappy`** → Public → Create.
(A repo with the same name as your username is your "profile README" repo.)

## 2. Upload these files
Easiest (GitHub Desktop or terminal), from inside this folder:
```bash
git init -b main
git add -A
git commit -m "🎏 the pond and the lab"
git remote add origin https://github.com/fizzyappy/fizzyappy.git
git push -u origin main
```
(Drag-and-drop upload on github.com also works, but make sure the hidden `.github` folder goes up too.)

## 3. Let the robot write
Repo → **Settings → Actions → General → Workflow permissions → Read and write** → Save.

## 4. Grow the first plate
Repo → **Actions → "grow the culture" → Run workflow**. After this it runs by itself every morning.

## 5. Test the pond
Click any koi button on your profile, press Submit. Within ~1 minute the issue gets a reply,
closes itself, and your koi swims in the pond.

---

### Things you can change
| what | where |
|---|---|
| name, roles, tagline, "off the screen" line | `lab/config.json` |
| projects, skills, wet-lab entries | `lab/config.json` |
| social links (shown under the footer) | `lab/config.json` → `links` |
| your art on the profile | drop up to 4 images in `art/` |
| a project logo | add `lab/<project-id>-logo.svg` (e.g. `saathi-logo.svg`) |

Every push to `lab/config.json`, `scripts/` or `art/` rebuilds the profile automatically.

### Profile polish (outside the README)
- Avatar → upload your own artwork.
- Pins → Finn, Saathi, Elementary, Human-Ink-Flipkart, Sonakshi-Sanyal-Website.
- Add descriptions + website links to Finn and Elementary; rename `Saathi-` → `Saathi`.
- Settings → Public profile → turn on **Include private contributions** if you commit to private repos
  (the dish then counts them too).
